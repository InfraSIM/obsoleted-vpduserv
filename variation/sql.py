#
# SNMP Simulator, http://snmpsim.sourceforge.net
#
# Managed value variation module: simulate a writable Agent using
# SQL backend for storing Managed Objects
#
# Module initialization parameters are dbtype:<dbms>,dboptions:<options>
#
# Expects to work a table of the following layout:
# CREATE TABLE <tablename> (oid text, tag text, value text, maxaccess text)
#
from snmpsim.grammar.snmprec import SnmprecGrammar
from snmpsim.mltsplit import split
from snmpsim import error, log
from pysnmp.smi import error as Error
import os

isolationLevels = {
    '0': 'READ UNCOMMITTED',
    '1': 'READ COMMITTED',
    '2': 'REPEATABLE READ',
    '3': 'SERIALIZABLE'
}


moduleContext = {}


def init(**context):
    options = {}
    if context['options']:
        options.update(
            dict([split(x, ':') for x in split(context['options'], ',')])
        )
    if 'dbtype' not in options:
        raise error.SnmpsimError('database type not specified')
    db = __import__(
        options['dbtype'],
        globals(), locals(),
        options['dbtype'].split('.')[:-1]
    )

    if 'dboptions' in options:
        connectParams = {'database': options['dboptions']}
    else:
        connectParams = dict(
            [(k, options[k]) for k in options if k in ('host', 'port', 'user',
                                                       'passwd', 'password',
                                                       'db', 'database',
                                                       'unix_socket',
                                                       'named_pipe')]
        )
        for k in 'port', 'connect_timeout':
            if k in connectParams:
                connectParams[k] = int(connectParams[k])
    if not connectParams:
        raise error.SnmpsimError('database connect parameters not specified')
    moduleContext['dbConn'] = dbConn = db.connect(**connectParams)
    moduleContext['dbTable'] = dbTable = options.get('dbtable', 'snmprec')
    moduleContext['isolationLevel'] = options.get('isolationlevel', '1')
    if moduleContext['isolationLevel'] not in isolationLevels:
        raise error.SnmpsimError('unknown SQL transaction isolation level %s' %
                                 moduleContext['isolationLevel'])

    if not os.path.exists("/tmp/inform"):
        os.mkfifo('/tmp/inform')

    try:
        moduleContext['inform'] = inform = os.open("/tmp/inform",
                                                   os.O_WRONLY | os.O_NONBLOCK)
    except Exception, ex:
        raise error.SnmpsimError('---> Infrasim: {0}: {1}'.format(Exception, ex))


def variate(oid, tag, value, **context):
    if 'dbConn' in moduleContext:
        dbConn = moduleContext['dbConn']
    else:
        raise error.SnmpsimError('variation module not initialized')

    cursor = dbConn.cursor()

    try:
        cursor.execute(
            'set session transaction isolation level %s' % moduleContext['isolationLevel']
        )
        cursor.fetchall()
    except:  # non-MySQL/Postgres
        pass

    if value:
        dbTable = value.split(',').pop(0)
    elif 'dbTable' in moduleContext:
        dbTable = moduleContext['dbTable']
    else:
        log.msg('SQL table not specified for OID %s' % (context['origOid'],))
        return context['origOid'], tag, context['errorStatus']

    origOid = context['origOid']
    sqlOid = '.'.join(['%10s' % x for x in str(origOid).split('.')])
    if context['setFlag']:
        if 'hexvalue' in context:
            textTag = context['hextag']
            textValue = context['hexvalue']
        else:
            textTag = SnmprecGrammar().getTagByType(context['origValue'])
            textValue = str(context['origValue'])
        cursor.execute(
            'select maxaccess,tag,value from %s where oid=\'%s\' limit 1' % (dbTable, sqlOid)
        )
        resultset = cursor.fetchone()
        if resultset:
            maxaccess = resultset[0]
            if maxaccess != 'read-write':
                return origOid, tag, context['errorStatus']

            value_written = textValue
            try:
                value_settings = {}
                value_settings = dict([split(x, '=') for x in split(resultset[2], ',')])
                print value_settings
                # if detected error mode, raise an error
                if 'mode' in value_settings and \
                        value_settings['mode'] == 'error':
                    raise Error.WrongValueError(name=origOid,
                                                idx=max(0,
                                                        context['varsTotal'] - context['varsRemaining'] - 1))
                elif 'mode' in value_settings and \
                    value_settings['mode'] == 'normal':
                    value_written = "mode=" + value_settings['mode'] + \
                        ",value=" + textValue
                else:
                    return origOid, tag, context['errorStatus']
            except Error.WrongValueError:
                cursor.close()
                raise Error.WrongValueError(name=origOid,
                                           idx=max(0, context['varsTotal'] - context['varsRemaining'] - 1))
            except:
                pass

            cursor.execute(
                'update %s set tag=\'%s\',value=\'%s\' where oid=\'%s\'' %
                (dbTable, textTag, value_written, sqlOid)
            )

            inform = moduleContext.get('inform')
            try:
                value = str(origOid) + " " + textValue
                written_len = os.write(inform, value)
                if written_len != len(value):
                    log.msg("--->Infrasim: Expected length %d, actual length %d\n" % (len(str(origOid)), written_len))
                    cursor.close()
                    return origOid, tag, context['errorStatus']
            except Exception, ex:
                log.msg("--->Infrasim: {0}".format(ex))
                cursor.close()
                return origOid, tag, context['errorStatus']

        else:
            cursor.close()
            raise Error.NoSuchInstanceError(name=origOid,
                   idx=max(0, context['varsTotal'] - context['varsRemaining'] - 1))

        if context['varsRemaining'] == 0:  # last OID in PDU
            dbConn.commit()
        cursor.close()
        return origOid, textTag, context['origValue']
    else:
        if context['nextFlag']:
            cursor.execute('select oid from %s where oid>\'%s\' order by oid limit 1' % (dbTable, sqlOid))
            resultset = cursor.fetchone()
            if resultset:
                origOid = origOid.clone(
                  '.'.join([x.strip() for x in str(resultset[0]).split('.')])
                )
                sqlOid = '.'.join(['%10s' % x for x in str(origOid).split('.')])
            else:
                cursor.close()
                return origOid, tag, context['errorStatus']

        cursor.execute('select tag, value from %s where oid=\'%s\' limit 1' % (dbTable, sqlOid))
        resultset = cursor.fetchone()
        cursor.close()

        if resultset:
            try:
                value_settings = {}
                value_settings = \
                    dict([split(x, '=') for x in split(resultset[1], ',')])
                print value_settings
                if 'mode' in value_settings:
                    return origOid, str(resultset[0]), str(value_settings['value'])
            except:
                pass
            return origOid, str(resultset[0]), str(resultset[1])
        else:
            return origOid, tag, context['errorStatus']

def shutdown(**context):
    dbConn = moduleContext.get('dbConn')
    if dbConn:
        if 'mode' in context and context['mode'] == 'recording':
            dbConn.commit()
        dbConn.close()

    inform = moduleContext.get('inform')
    if inform:
        os.close(inform)
