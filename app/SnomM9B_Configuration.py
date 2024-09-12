#!/usr/bin/python3

import rtx8200_pb2
import wrappers_pb2
import sys
import logging

from lxml import etree as ET
import lxml.builder
from copy import deepcopy

from basic_utils.core import (
    clear,
    getattrs,
    map_getattr,
    rgetattr,
    rsetattr,
    slurp,
    to_string
)

import pandas as pd
import base64

import os
import sqlite3


class HTTPRequestError(Exception):
    pass


class SnomM9BConfiguration:

    def __init__(self, excel_file, logger=logging.getLogger('SnomM9BConfiguration')):
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        logger.addHandler(ch)
          
        self.logger = logger
        self.excel_file = excel_file
        
        # holds one gateway config set
        self.c = rtx8200_pb2.ConfigSettings()
        self.data = self.read_xls_into_data(self.excel_file)
        
        # DB
        self.db = None
        self.db_filename = None
        self.schema_filename = None
        self.createDB()


    def update_ConfigSettings_from_excel_file(self, excel_file):
        self.logger.debug("update_ConfigSettings_from_excel_file:", self.data)

        self.data = None
        self.data = self.read_xls_into_data(excel_file)
        
        self.logger.debug("update_ConfigSettings_from_excel_file: %s" %  self.data)

        
    def read_xls_into_data(self, file):
        self.logger.info("read_xls_into_data: Read xls file %s" % file)

        data_from_excel = pd.read_excel(file)
        
        return data_from_excel

    def set_ConfigSetting_from_excel_data(self, data, column, line):
        val=None
        
        self.logger.debug('excel_data: start-----------------------------------------------------')

        # check if we have a beacon type
        self.logger.debug("excel_data: %s" % data.columns[column][2:])
        if 'eaconSettings' in data.columns[column][2:] :
            self.logger.debug("excel_data: beacon detected")
            #print('beacon detected')
            protobuf_set = self.beacon
        else:
            self.logger.debug("excel_data: self.c detected")
            protobuf_set = self.c
            
        try:
            # check if value is ENUM type
            val = getattr(rtx8200_pb2, data[data.columns[column]][line])
            self.logger.debug("excel_data: %s with ENUM: %s" % (data.columns[column], data[data.columns[column]][line]))

        except (AttributeError, TypeError, ValueError, ) as e:
            #print(data.columns[column], 'is not an ENUM', e)
            # get the type from line 0 of excel. This must be the correct data-type
            try:
                # in case c.name name does not exist we cannot get a type, nTypeError
                protobuf_type = type(rgetattr(protobuf_set, data.columns[column][2:]))
                #print('protobuf_type=', protobuf_type)
                self.logger.debug("excel_data: protobuf_type=%s" % protobuf_type)

                # check if we get a string  which needs to be a bytes sequence
                val = data[data.columns[column]][line]
                if type(val) is str and protobuf_type is bytes:
                    self.logger.debug("excel_data: A string instead of a byte sequence, try to decode to bytes %s" % val)

                    # convert string from utf-8 to ascii
                    #val = val.encode('ascii', 'replace')
                    val = val.replace("0x", "")
                    val = bytes.fromhex(str(val))
                else:
                    val = protobuf_type(val)

            except (TypeError, AttributeError) as e:
                self.logger.debug("excel_data: Error - unknown c.name name.::%s" % e)
                
        # take the next line of config data of setting with column name
        # check for type incompatibilites and wrong column key name in excel(data)
        try:
            #print(data.columns[column], 'with value:', val)
            self.logger.debug("excel_data: %s with value: %s" % (data.columns[column], val))

            rsetattr(protobuf_set, data.columns[column][2:], val)
        except (TypeError, ValueError) as e:
            #print('Error (TypeError, ValueError)::', e)
            self.logger.debug("excel_data: Error (TypeError, ValueError)::%s" % e)

        except (AttributeError, KeyError) as e:
            #print('Error (AttributeError, KeyError)::', e)
            self.logger.debug("excel_data: Error (AttributeError, KeyError)::%s" % e)

        self.logger.debug('excel_data: end-------------------------------------------------------')


    #

    # generate the XML provisioning file
    # <configs>
    #   <devices>
    #       <device type="rtx8200" ipei="0328D3C909" revision="1.0">
    #           <data encoding="base64">CgQIARABEjYKFFJUWDgyMDAgSGVsbG8gV29ybGQhEgoxMjM0NTY3ODkwGgoxMTIyMzM0NDU1IgAqAggBMAEaCQoCCBoSAwjgEiIICAQYASABKAIqPgocChoKEEFBQUFBQUFBQUFBQUFBQUESAhERGgIiIgoaEhgKFEJCQkJCQkJCQkJCQkJCQkJCQkJCEDMSAghkMiQIAxABGhwIAhICCBQaFGBgYGBgYGBgYGBgYGBgYGBgYGBgMAQ=b'CgQIARABEjYKFFJUWDgyMDAgSGVsbG8gV29ybGQhEgoxMjM0NTY3ODkwGgoxMTIyMzM0NDU1IgAqAggBMAEaCQoCCBoSAwjgEiIICAQYASABKAIqPgocChoKEEFBQUFBQUFBQUFBQUFBQUESAhERGgIiIgoaEhgKFEJCQkJCQkJCQkJCQkJCQkJCQkJCEDMSAghkMiQIAxABGhwIAhICCBQaFGBgYGBgYGBgYGBgYGBgYGBgYGBgMAQ='
    #           </data>
    #       </device>
    #   </devices>
    # </configs>
    def createFullConfigXML(self):
        E = lxml.builder.ElementMaker()
        CONFIGS = E.configs
        DEVICES = E.devices
        DEVICE  = E.device
        DATA  = E.data

        config_doc = CONFIGS(
                            DEVICES()
                            )
        # clear old serialized data
        self.c = rtx8200_pb2.ConfigSettings()

        # get excel data
        data = self.data
        # add <device> from configSettings  under <devices>
        devices = config_doc.find("devices")

        numGateways = data.shape[0]
        numSettings = data.shape[1]
        
        # add beacon if requested in excel.
        if not data.filter(regex='eaconSettings').empty:
            # get a beacon as well.
            self.logger.debug('excel_data: add beacon ID')
            print(data.filter(regex='eaconSettings'))
            self.beacon = self.c.txModeSettings.beaconId.add()
        else:
            self.logger.debug('excel_data: NO beacon ID')
            self.beacon = None
            
        print('Add', numSettings, 'settings for', numGateways)
        for i in range(0,numGateways,1):
            for column in range(0,numSettings,1):
                # example::
                # set_ConfigSetting_from_excel_data(data, 8, i)

                # example with ENUM
                # c.generalSettings.alarmSettings             = rtx8200_pb2.POWER_BATTERY_LOW
                # c.generalSettings.alarmSettings             = getattr(rtx8200_pb2, str(data['c.generalSettings.alarmSettings'][i]))
                # set_ConfigSetting_from_excel_data(data, 9, i)
              
                self.set_ConfigSetting_from_excel_data(data, column, i)

            # use config to generate byte stream
            data_stream = base64.b64encode(self.c.SerializeToString())
            data_stream = data_stream.decode('ascii')
            devices.insert(1,DEVICE(DATA(data_stream, encoding="base64"), type="rtx8200", ipei=str(data['c.IPEI'][i]), revision=str(data['c.revision'][i])))
            
            # insert in db.. this will not be deleted for all users
            self.update_db(data['c.IPEI'][i], "rtx8200", str(data['c.revision'][i]), data_stream)
            
            #devices.insert(1,DEVICE(DATA(data_stream), type="SnomM9B", ipei=str(data['c.IPEI'][i]), revision=str(data['c.revision'][i])))

        #xml_with_header  = ET.tostring(config_doc, encoding='unicode')
        return config_doc
        
    # create XML for one IPEI
    def createIPEIConfigFromXML(self, xml_doc, ipei, revision=1):
#        tree=xml_doc
#
#        for bad in tree.xpath('/configs/devices/device[not(@ipei="%s")]' % ipei):
#          # here I grab the parent of the element to call the remove directly on it
#          bad.getparent().remove(bad)
          
          
        # return XML from DB
        E = lxml.builder.ElementMaker()
        CONFIGS = E.configs
        DEVICES = E.devices
        DEVICE  = E.device
        DATA  = E.data

        config_doc = CONFIGS(
                                DEVICES()
                            )
        # Revision of configuration. RTX8200 is only provisioned if this differs
        # from the internal revision of the RTX8200.
        # we assume a new revision every time!
        # cycle the revision from 1 to 3
        print('Base request revision=', revision)
        revision = (int(revision) % 3) + 1
        print('sending data with new revision=', revision)
        
        db_data = self.read_db(ipei, "rtx8200", str(revision))
        print('createIPEIConfigFromXML from DB:', db_data)
        
        if db_data != "":
            devices = config_doc.find("devices")
            devices.insert(1,DEVICE(DATA(db_data, encoding="base64"), type="rtx8200", ipei=str(ipei), revision=str(revision)))
        
        tree = config_doc
        print(ET.tostring(tree, encoding='unicode'))

        return tree
        
    def getDataWithIPEIFromXML(self, xml_doc, ipei, revision=3):
        tree=xml_doc
            
#        data = tree.xpath('//device[@ipei="%s"]/data/text()' % ipei)
#        print('getData:', data)
        
        # read data from DB
        ## ??? fixed revision !!
        # construct an XML answer!
        
        db_data = self.read_db(ipei, "rtx8200", revision)
        print('getDataWithIPEIFromXML from DB:', db_data)
        
        return db_data
        
        
    # create XML without data tags
    def createNoDataConfigFromXML(self, xml_doc, list_of_ipeis=None):
        tree=xml_doc
        
        # return XML from DB
        E = lxml.builder.ElementMaker()
        CONFIGS = E.configs
        DEVICES = E.devices
        DEVICE  = E.device
         
        config_doc = CONFIGS(
                              DEVICES()
                            )
           
        # get all devices revisions from ipeis
        for ipei in list_of_ipeis:
            #print(ipei)
            record = self.read_db_ipei(ipei)
            #print('Record::', record)
            
            if record is not "":
                devices = config_doc.find("devices")
                #devices.insert(1,DEVICE(type=record[0], ipei=str(ipei), revision=str(record[1])))
                # we use a revision which never matches the revision in the Gateway
                # as a result, the base will always request data for every ipei.
                devices.insert(1,DEVICE(type=record[0], ipei=str(ipei), revision="4"))

        tree = config_doc
        print(ET.tostring(tree, encoding='unicode'))

        return tree
 
 
    def read_db_ipei(self, ipei):
        #print(ipei, type, revision)
        connection = sqlite3.connect(self.db_filename)
        if connection:
            with connection as conn:
                cur = conn.cursor()

                # get the db record
                insert_query = """
                                SELECT type,revision from SnomM9BDevices where ipei=?
                            """
                recordTuple = (ipei, )
                cur.execute(insert_query, recordTuple)
                     
                #print(insert_query)
                rows = cur.fetchone()
                #print(rows)
                if not rows:
                    return("")
                else:
                    return(rows)
        else:
            print('read_db_ipei: Connection does not exist, do nothing')
         

    def read_db(self, ipei, type, revision):
        #print(ipei, type, revision)
        connection = sqlite3.connect(self.db_filename)
        if connection:
            with connection as conn:
                cur = conn.cursor()

                # get the db record
                insert_query = """
                                 SELECT data from SnomM9BDevices where ipei=? and revision=?
                             """
                recordTuple = (ipei, revision, )
                cur.execute(insert_query, recordTuple)
                      
                #print(insert_query)
                rows = cur.fetchone()
                if not rows:
                    return("")
                else:
                    for row in rows:
                        return(row)
        else:
            print('read_db: Connection does not exist, do nothing')
          

    def update_db(self, ipei, type, revision, data):
        #print(ipei, type, revision, data)
        connection = sqlite3.connect(self.db_filename)
        if connection:
            with connection as conn:
                cur = conn.cursor()

                # sqlite in python is below 3.24 version which supports UPSERT
#                insert_query = """
#                    INSERT INTO SnomM9BDevices (ipei, type, revision, data) VALUES (?, ?, ?, ?)
#                        ON CONFLICT (ipei, revision) DO UPDATE SET
#                            type=excluded.type, revision=excluded.revision, data=excluded.data
#                """
                # instead use INSERT OR REPLACE INTO
                insert_query =  """
                                   INSERT OR REPLACE INTO SnomM9BDevices (ipei, type, revision, data) VALUES (?, ?, ?, ?)
                               """
                
                #print(insert_query)
                recordTuple = (ipei, type, revision, data, )
                #print(recordTuple)

                cur.execute(insert_query, recordTuple)
                
                #cur.execute('SELECT * from SnomM9BDevices')
                #print(cur.fetchall())
                     
                conn.commit()
                # conn.close()
        else:
            print('update_db: Connection does not exist, do nothing')
        

    def createDB(self):
        self.db_filename = 'DB/SnomM9BProvisioning.db'
        self.schema_filename = 'DB/SnomM9BProvisioningSchema.sql'

        db_is_new = not os.path.exists(self.db_filename)

        conn = sqlite3.connect(self.db_filename)

        if db_is_new:
            print('Creating schema')
            with open(self.schema_filename, 'rt') as f:
                schema = f.read()
                conn.executescript(schema)

                print('Inserting initial data')
                conn.executescript("""
                insert into SnomM9BDevices (ipei, type, revision, data)
                values ('0000000000', 'type1',
                        '1', 'abcdefghijklmnopqrstuvwxyz');
                insert into SnomM9BDevices (ipei, type, revision, data)
                values ('0000000001', 'type2',
                        '2', 'abcdefgh');
                """)

        else:
            print('Database exists, assume schema does, too.')

        conn.close()


import argparse

if __name__ == '__main__':
    logger = logging.getLogger('mySnomM9BConfig')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    logger.addHandler(ch)

    parser = argparse.ArgumentParser(description='Input Parameter: xlsx')
    parser.add_argument('xlsx_file', type=str,
                        help='Excel Gateqway collection')
    
    results = parser.parse_args()

    logger.debug("commandline args:", results)
    
    conf = SnomM9BConfiguration(results.xlsx_file)
    
#    # usage: python3 SnomM9B_Configuration.py SnomM9BConfigurationSet.xlsx
#    if sys.argv[1] is not None:
#        conf = SnomM9BConfiguration(sys.argv[1])
#    else:
#        conf = SnomM9BConfiguration('./SnomM9BConfigurationSetSnom.xlsx')
#
        
    xml_full = conf.createFullConfigXML()
    
    xml_with_header = ET.tostring(xml_full, pretty_print=True, doctype='<?xml version="1.0" encoding="utf-8"?>', encoding='unicode')
    
    print(xml_with_header)
    
    xml_oneIPEI = deepcopy(xml_full)
    xml_oneIPEI = conf.createIPEIConfigFromXML(xml_oneIPEI, '0328D3C909')
    xml_with_header = ET.tostring(xml_oneIPEI, pretty_print=True, doctype='<?xml version="1.0" encoding="utf-8"?>', encoding='unicode')
    
    print(xml_with_header)
    
    xml_nodata = deepcopy(xml_full)
    list_of_ipeis = ["0328D3C909"]
    xml_nodata = conf.createNoDataConfigFromXML(xml_nodata, list_of_ipeis)
    xml_with_header = ET.tostring(xml_nodata, pretty_print=True, doctype='<?xml version="1.0" encoding="utf-8"?>', encoding='unicode')

    print(xml_with_header)
    
    conf.createDB()
    conf.update_db("0000000000", "typeXXX", 1, "bbbb1")
    conf.update_db("0000000000", "typeXXX", 2, "bbbb2")
    conf.update_db("0000000000", "typeXXX", 3, "bbbb3")
    conf.update_db("0000000000", "typeXXX", 1, "bbb11")

    # read data
    print(conf.read_db("0000000000", "typeXXX", 1))
    print(conf.read_db("0000000000", "typeXXX", 3))
        
#
#    print('Original', ET.tostring(xml_full, pretty_print=True, encoding="unicode"))
#
#    xml_nodata = conf.createNoDataConfigFromXML(xml_full)
#    print(ET.tostring(xml_nodata, pretty_print=True, encoding="unicode"))
