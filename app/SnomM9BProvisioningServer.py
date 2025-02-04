#!/usr/bin/python
# vi:si:et:sw=4:sts=4:ts=4
# -*- coding: UTF-8 -*-
# -*- Mode: Python -*-
import bottle
import os
#import multiprocessing
import logging
#import random

#import datetime
import time

from bottle import Bottle, app, run, static_file, template, request, response, FormsDict
#from multiprocessing import Process, Queue, cpu_count
from beaker.middleware import SessionMiddleware

#from bottle_utils import html
from bottle_utils.i18n import I18NPlugin
from bottle_utils.i18n import lazy_ngettext as ngettext, lazy_gettext as _

from bottle import jinja2_view, route

from copy import deepcopy
import subprocess
import shutil


template.settings = {
    'autoescape': True,
}

from bottle import url

from lxml import etree as ET
import SnomM9B_Configuration as M9BC
from RSyslogParser import RSyslogParser

template.defaults = {
    'url': url,
    'site_name': 'SnomM9BProvisioningServer',
}

LANGS = [
         ('de_DE', 'Deutsch'),
         ('en_US', 'English')
         #('fr_FR', 'français'),
         #('es_ES', 'español')
         ]

DEFAULT_LOCALE = 'en_US'
LOCALES_DIR = './locales'


session_opts = {
    'session.type': 'file',
    'session.cookie_expires': 300,
    'session.data_dir': '/tmp/data',
    'session.auto': True,
    'session.encrypt_key': 'invoipwetrust',
    'session.validate_key': 'invoipwetrust'
}


bottle.debug(True)
# used for templates with multiple urls to download images etc.

bottle.TEMPLATE_PATH=("./views", "./templates")
css_root="/css/"
css_root_path = ".%s" % css_root
images_root="/images/"
images_root_path = ".%s" % images_root
config_root="/conf/"
config_root_path = ".%s" % config_root
save_root="/uploads/"
save_root_path = ".%s" % save_root

tapp = bottle.default_app()
wsgi_app = I18NPlugin(tapp,
            langs=LANGS,
            default_locale=DEFAULT_LOCALE,
            locale_dir=LOCALES_DIR,
            domain='base'
)
app = SessionMiddleware(wsgi_app, session_opts)

from bottle import Jinja2Template


logger = logging.getLogger('M9BPS')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
logger.addHandler(ch)

## helper
class PrettyFormsDict(FormsDict):
    
    def __repr__(self):
        # Return a string that could be eval-ed to create this instance.
        args = ', '.join('{}={!r}'.format(k, v) for (k, v) in sorted(self.items()))
        return '{}({})'.format(self.__class__.__name__, args)
    
    def __str__(self):
        # Return a string that is a pretty representation of this instance.
        args = ' ,\n'.join('\t{!r}: {!r}'.format(k, v) for (k, v) in sorted(self.items()))
        return '{{\n{}\n}}'.format(args)
## end helper

'''
@bottle.hook('before_request')
def setup_request():
    request.session = request.environ['beaker.session']
    #print('beaker_session:', request.environ['beaker.session'])
    Jinja2Template.defaults['session'] = request.session
    # check if the session is still valid / check login status
'''

'''
@bottle.hook('before_request')
def before_request():
    path_info = bottle.request.environ.get('PATH_INFO')
    query_string = bottle.request.environ.get('QUERY_STRING')
    full_path_reconstructed = path_info + (f"?{query_string}" if query_string else "")
    print("Full Path (reconstructed):", full_path_reconstructed)
'''


# absolute css path
@bottle.get('/css/<filename>')
def load_css(filename):
    return static_file(filename, root="%s" % (css_root_path))

@bottle.get('/<filepath:path>/css/<filename>')
def load_css(filepath, filename):
    #    print("%s..%s." % (images_root_path, filepath))
    return static_file(filename, root="%s" % (css_root_path))

@bottle.get('/images/<filename>')
def load_image(filename):
    return static_file(filename, root="%s" % (images_root_path))

@bottle.get('/<filepath:path>/images/<filename>')
def load_image(filepath, filename):
    return static_file(filename, root="%s" % (images_root_path))


@bottle.route('%s<filepath:path>' % config_root, no_i18n = True)
def send_static(filepath):
    return static_file(filepath, root=config_root_path)


@bottle.route('/config', name='M9BDevices', no_i18n=True, method='GET')
def M9BDevicesRequest():
    global xml_full
#    xml_full = conf.createFullConfigXML()
    

#    s = bottle.request.environ.get('beaker.session')
#    logger.debug("Session:", s)
#
#    xml_fully = ET.fromstring(s['xml_full'])
#
#    print(xml_fully)
    list_of_ipeis = request.query.getall('ipei')

    response.headers['Content-Type'] = 'xml/application'
    response.headers['Content-Type'] = 'text/html'

    # return xml without data
    xml_nodata = deepcopy(xml_full)
    xml_nodata = conf.createNoDataConfigFromXML(xml_nodata, list_of_ipeis)
    xml_with_header = ET.tostring(xml_nodata, pretty_print=True, doctype='<?xml version="1.0" encoding="utf-8"?>', encoding='unicode')

    return xml_with_header


@bottle.route('/config/data', name='M9BDeviceData', no_i18n=True, method='GET')
def M9BDeviceDataRequest():
    global xml_full
    get_params = request.query.decode()
    print(get_params)
    if "ipei" in get_params:
        ipei = get_params['ipei']
    else:
        ipei="0000000000"
    if "revision" in get_params:
        revision = get_params['revision']
    else:
        revision=1
    
    #print(ipei, revision)
    
    response.headers['Content-Type'] = 'xml/application'
    response.headers['Content-Type'] = 'text/html'
    # return xml from ipei including data
    xml_oneIPEI = deepcopy(xml_full)
    xml_oneIPEI = conf.createIPEIConfigFromXML(xml_oneIPEI, ipei, revision)
    xml_with_header = ET.tostring(xml_oneIPEI, pretty_print=True, doctype='<?xml version="1.0" encoding="utf-8"?>', encoding='unicode')
      
    return xml_with_header
    
    
'''
    protoc --decode rtx8200.ConfigSettings --proto_path="protobuf" rtx8200.proto< 8200.bin
    settingsVersion {
      major: 1
      minor: 1
    }
    generalSettings {
      name: "SnomM9B-1"
      alarmServerAddress: "6660"
      beaconServerAddress: "6661"
      configurationMode {
      }
      surveyMode {
        value: true
      }
    }
    rxModeSettings {
      proximityMode: NOTIFY_WHEN_EITHER
      sensitivitySetting: SENSITIVITY_MINIMUM
      rxModeFilter {
        filterBeaconType: IBEACON
      }
      statusUpdateInterval {
        value: 10
      }
      statusUpdateRssiDiff {
        value: 2
      }
      proximityAlgorithm: ALGORITHM4
    }

'''
@bottle.route('/data/show', name='ShowM9BDeviceData', no_i18n=False, method='GET')
def ShowM9BDeviceDataRequest():
    global xml_full
    get_params = request.query.decode()
    print(get_params)
    if "ipei" in get_params:
        ipei = get_params['ipei']
    else:
        ipei="0000000000"
    if "revision" in get_params:
        revision = get_params['revision']
    else:
        revision=1
          
    response.headers['Content-Type'] = 'text/html'
    # return xml from ipei including data
    xml_oneIPEI = deepcopy(xml_full)
    data = conf.getDataWithIPEIFromXML(xml_oneIPEI, ipei, revision)
    
#    protoc --decode rtx8200.ConfigSettings --proto_path="protobuf" rtx8200.proto< 8200.bin
    
    #data_str = bytes(data[0], encoding='ascii')
    data_str = bytes(data, encoding='ascii')

    try:
        f = open('/tmp/8200.bin', 'w')
        f.close()

        os.remove(f.name)
    except:
        logger.warning('couldnt delete bin file')
        pass
    try:
        # try to stay OS path compatible
        base64_command = shutil.which("base64")

        protoMessage = subprocess.Popen("%s --decode > /tmp/8200.bin" % base64_command,
        stdin=subprocess.PIPE, shell=True)
        protoMessage.communicate(data_str)
        
        myinput = open('/tmp/8200.bin')
        ## docker needs /usr/bin path ????
        #result = subprocess.Popen("/usr/bin/protoc --decode rtx8200.ConfigSettings --proto_path=protobuf protobuf/rtx8200.proto",
#            stdin=myinput, stdout=subprocess.PIPE, shell=True )
        
        # try to stay OS path compatible
        protoc_command = shutil.which("protoc")
          
        result = subprocess.Popen("%s --decode rtx8200.ConfigSettings --proto_path=protobuf protobuf/rtx8200.proto" % protoc_command,
             stdin=myinput, stdout=subprocess.PIPE, shell=True )
        #protoMessage.communicate(myinput)
        out, err = result.communicate()
        #print(out, err)
        myinput.close()
        
        if not err:
            err=bytes('SUCCESS with ipei=%s and revision=%s' % (ipei, revision), encoding="ascii")
    except:
        err=bytes('Failed to convert/load data', encoding="ascii")
        out=bytes('Failed to convert/load data', encoding="ascii")
        
    return  bottle.jinja2_template('show', title=_("M9BShowData"), data=out.decode(encoding="utf-8"), err=err.decode(encoding="utf-8"), ipei=ipei)
    

@bottle.route('/upload', no_i18n=True, method='POST')
def do_upload():
    global conf
    global xml_full

    category = request.forms.get('file')
    upload = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    if ext not in ('.xls', '.xlsx'):
        return "File extension not allowed."
    
    if not os.path.exists(save_root_path):
        os.makedirs(save_root_path)

    # get a timestamp for the file
    ts = int(time.time())
    file_path = "{path}/{ts}{file}".format(path=save_root_path, ts=ts, file=upload.filename)
    upload.save(file_path)
    
    conf.update_ConfigSettings_from_excel_file(file_path)
    xml_full= None
    xml_full = conf.createFullConfigXML()
    xml_with_header = ET.tostring(xml_full, pretty_print=True, doctype='<?xml version="1.0" encoding="utf-8"?>', encoding='unicode')
           
    logger.debug(f"XML on upload: {xml_with_header}")

    logger.debug("File successfully loaded and stored '{0}'.".format(xml_with_header))
    return bottle.jinja2_template('main', title=_("M9BPS"), data=xml_with_header)

def get_syslog(syslog_file, grep_argument = 'PP_'):
    # try to stay OS path compatible
    grep_command = shutil.which("grep")
    tail_command = shutil.which("tail")
    
    try:
#        result = subprocess.Popen("/usr/bin/tail -n 100 %s" % syslog_file,
        result = subprocess.check_output("%s -n 100 %s | %s %s" % (tail_command, syslog_file,  grep_command, grep_argument), shell=True )
        
        if not result:
            err=bytes('empty syslog file', encoding="ascii")
    except subprocess.CalledProcessError as e:
        print(e)
        result=bytes('Failed to load or empty syslog data', encoding="ascii")
        
    return result


import validators

def RepresentsInt(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

@bottle.route('/trigger', name='trigger', method=['POST', 'GET'])
def run_trigger():
    
    baseIPPort = request.forms.get('baseIP')
    syslogFilter = request.forms.get('syslogFilter')
    testIPEI = request.forms.get('testIPEI')
    
    # split and check ip and port
    print(baseIPPort)
    if not baseIPPort:
            baseIP = "10.110.11.114"
            basePort = "80"
    else:
        x = baseIPPort.split(":", 1)
        baseIP = x[0]
        if not validators.ip_address.ipv4(baseIP):
            baseIP = "10.110.11.114"
        
        if len(x) != 2:
            basePort = "80"
        else:
            basePort = x[1]
        if not RepresentsInt(basePort):
            basePort = "80"
        if not validators.between(int(basePort), min=10, max=65535):
            basePort = "80"

    # docker change to local path
    syslog_file="/usr/src/app/log/%s.log" % baseIP
          
    # combine again.
    print(baseIPPort, baseIP, basePort)
    baseIP = "%s:%s" % (baseIP, str(basePort))
    
    if not syslogFilter:
        syslogFilter = "\"\""
    if not testIPEI:
         testIPEI = "0328D3C8FC"
    syslog_data = get_syslog(syslog_file, syslogFilter)
    
    # scan syslog for known messages and give hints.
    parser = RSyslogParser()

    syslog_analysis_list = parser.analyse_syslog(syslog_file,100)
    #print(syslog_analysis_list)
    
    return bottle.jinja2_template('trigger', title=_("M9BPS"), testIPEIval=testIPEI, baseIPval=baseIP, syslogFilterval=syslogFilter, data=xml_with_header, syslog_data=syslog_data.decode(encoding="utf-8"), syslog_analysis_list=syslog_analysis_list )


@bottle.route('/db_dump', name='db_dump', method='GET')
def run_db_dump():
    try:
        result = subprocess.check_output("sqlite3 DB/SnomM9BProvisioning.db 'SELECT * from SnomM9BDevices ORDER BY ipei'", shell=True )
        
        if not result:
            err=bytes('empty db', encoding="ascii")
    except subprocess.CalledProcessError as e:
        print(e)
        result=bytes('Failed to load or empty db', encoding="ascii")
        
    return result


@bottle.route('/', name='main', method='GET')
def run_main():
    global xml_full
    
    s = bottle.request.environ.get('beaker.session')
    s['test'] = s.get('test',0) + 1
    s.save()
#
    # initialize provisioning XML docs
    xml_with_header = ET.tostring(xml_full, pretty_print=True, encoding='unicode')
    # store xml data in web session
    s['xml_full'] = ET.tostring(xml_full, pretty_print=True, encoding='unicode')
   
    return bottle.jinja2_template('main', title=_("M9BPS"), data=xml_with_header)


# docker change to local listen
# run web server
#host = "10.245.0.28"
host = "0.0.0.0"
#host = "192.168.188.21"
#host = "10.110.16.75"
#host = "192.168.188.21"
#host = "10.110.23.69"

global conf
global syslog_file

conf = M9BC.SnomM9BConfiguration('./SnomM9BConfigurationSet.xlsx')
       
xml_full = conf.createFullConfigXML()
xml_with_header = ET.tostring(xml_full, pretty_print=True, doctype='<?xml version="1.0" encoding="utf-8"?>', encoding='unicode')
logger.debug(f"XML on upload: {xml_with_header}")

p=RSyslogParser()

bottle.run(app=app, host=host, port=8080, reloader=True, debug=True)
