#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
    Mar 16 18:54:12 192.168.188.105 000413b606b1[Ben] 00033 -[ DHCP Discover completed]


    Mar 17 10:37:57 192.168.188.105 000413b606b1[Ben] 01953 -[ PP_PROV_PROXY: HandleSrvResyncInd: IPEI:0328D3C909]
    

"""

import pandas as pd
from pyparsing import Word, hexnums, alphas, Suppress, Combine, nums, string, Regex
from time import strftime
import subprocess

from bottle_utils.i18n import lazy_ngettext as ngettext, lazy_gettext as _

class RSyslogParser(object):
    def __init__(self):
        ints = Word(nums)
        
        # timestamp
        month = Word(string.ascii_uppercase, string.ascii_lowercase, exact=3)
        day   = ints
        hour  = Combine(ints + ":" + ints + ":" + ints)
        
        # still 3 fields in pattern
        timestamp = Combine(month + Regex("..") + day + " " + hour)
        
        # hostname
        #hostname = Word(alphas + nums + "_" + "-" + ".")
        ip_address = Combine(ints + "." + ints + "." + ints + "." + ints)
        
        # appname
        mac = Word(hexnums, exact=12)
        mac_extra = Combine("[" + Word(alphas) + "]")
        id = ints
        
        # message still has ending ']'
        message = Combine(Suppress('-[') + Regex(".*(?=[\]]*])"))
        #message = Regex(".*")

        # pattern build
        self.__pattern = timestamp + ip_address + mac + mac_extra + id + message
        #print(self.__pattern)
        
    
    def parse(self, line):
        #print('line:',line)
        parsed = self.__pattern.parseString(line)
        
        print(parsed)
        payload              = {}
        #payload["priority"]  = parsed[0]
        payload["timestamp"]    = parsed[0]
        payload["ip_address"]   = parsed[1]
        payload["mac"]          = parsed[2]
        payload["mac_extra"]    = parsed[3]
        payload["id"]           = parsed[4]
        payload["message"]      = parsed[5]
        
        return payload


    def tail(self, f, n, offset=0):
        proc = subprocess.Popen(['tail', '-n', '%s' % (n + offset), f], stdout=subprocess.PIPE, encoding='utf-8')
        lines = proc.stdout.readlines()
        proc.wait()
        
        return lines


    def grep_syslog(self, line, pattern=".*PP_.*"):
        try:
            #print(line)
            pattern = Regex(pattern)
            parsed = pattern.parseString(line)
            return(parsed)
        except:
            return False
            
            
    def analyse_syslog(self, file, num_lines=100):
    
        syslogFileContent = self.tail(file, num_lines)
        
        #print(syslogFileContent)
        list1 = []
        for line in syslogFileContent:
            fields = self.parse(line)
            #print(line)

            fields['severity'] = 'alert-info'
            append=False

            if self.grep_syslog(fields['message'], ".*PP_.*"):
                fields['answer']=_("PP_ Info")
                fields['severity'] = 'alert-info'
                append=True

            if self.grep_syslog(fields['message'], ".*HandleXmlDeviceInd:.IPEI.*"):
                fields['answer']=_("Provisioning answer: Gateway Config received for this IPEI.")
                fields['severity'] = 'alert-success'
                append=True

            if self.grep_syslog(fields['message'], ".*Send.b64.CONFIG.*BTCFG.*"):
                fields['answer']=_("Sending Payload. Check, if this is the desired revision.")
                fields['severity'] = 'alert-success'
                append=True
                # now check if this is just the command
                if self.grep_syslog(fields['message'], ".*={1}.+={1}"):
                    fields['answer']=_("End of Payload.")
                    fields['severity'] = 'alert-success'
                    append=True
                else:
                    if self.grep_syslog(fields['message'], ".*=="):
                        fields['answer']=_("Prepare to send payload.")
                        fields['severity'] = 'alert-info'
                        append=True

            if self.grep_syslog(fields['message'], ".*PP_PROV_PROXY:.Receive.SMS.status.code:.00.*"):
                fields['answer']=_("Provisioning succesful, check data with handset.")
                fields['severity'] = 'alert-success'
                append=True

            if self.grep_syslog(fields['message'], ".*PP_PROV_SEGMENT_REQ.SegNo:1.*"):
                fields['answer']=_("Gateway received provisioning data.")
                fields['severity'] = 'alert-info'
                append=True
          
            if self.grep_syslog(fields['message'], ".*PP_PROV_TRANSACTION_TIMEOUT.*"):
                fields['answer']=_("received \"Excel Upload contains errors\" or Provisioning Server is not answering. Not running? Wrong IP in  Management/Location Gateway specified?")
                fields['severity'] = 'alert-danger'
                append=True
        
            if self.grep_syslog(fields['message'], ".*JobInd.from.FP.failed.*"):
                fields['answer']=_("Management/Text Messaging is not enabled. Please enable Messaging")
                fields['severity'] = 'alert-danger'
                append=True

            if self.grep_syslog(fields['message'], ".*ProtoBuf.decode.failed.with.error.*"):
                fields['answer']=_("Excel Upload contains errors. Refer to the error code list and correct.")
                fields['severity'] = 'alert-danger'
                append=True

            if self.grep_syslog(fields['message'], ".*Handle.revision.request.*"):
                fields['answer']=_("Check Revision and make sure you have rev+1 ready for provisioning")
                fields['severity'] = 'alert-info'
                append=True
                
            if append:
                list1.append(fields)

        return list1


def main():
    
    parser = RSyslogParser()
    
    syslogFile = '/Users/oliver.wittig/Downloads/snom-1/Wismar/log/10.110.30.105.log'
    
    list = parser.analyse_syslog(syslogFile,100)
    print(list)

if __name__ == "__main__":
    main()
