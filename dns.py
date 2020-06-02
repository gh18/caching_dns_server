import dnslib
import socket
from datetime import datetime
import time, threading
import pickle
import sys

"""
Корнеев Михаил, КН-203 (ИЕНиМ-280208)
"""

PORT = 53
LOCAL_HOST = '127.0.0.1'
FORWARDER = '8.8.4.4'                           # one of Google Public DNS servers
CACHE_TIME_CHECK = 360
# dns.adguard.com
FORWARDER_2 = '176.103.130.130'


def set_forwarding_address():
    """Provides an option to choose forwarding DNS server"""
    try:
        custom_forwarder = input('Specify FORWARDER ip_address: ')
        if custom_forwarder:
            return custom_forwarder
        else:
            return FORWARDER_2
    except EOFError as ex:
        print('Invalid input: Error was raised - ' + str(ex))
        raise SystemExit
        # sys.exit(1)


def write_cache(data):
    """Saves cache to file (binary format)"""
    file = open('cache', 'wb')
    pickle.dump(data, file)
    file.close()


def read_cache():
    """Downloads existing cache from a file (binary format)"""
    try:
        file = open('cache', 'rb')
        _cache = pickle.load(file)
        file.close()
        return _cache
    except (FileNotFoundError, OSError, EOFError) as ex:
        print(ex)
        return dict()


# A simple way to do timed checks (since we don't need the Timer outside this script
# (when dns.py is killed Timer gets killed too)) -> PROBLEM: we make it a shared resource!
# def clean_cache_by_ttl():
#     threading.Timer(CACHE_TIME_CHECK, read_and_delete).start()
#
# 
# def read_and_delete():
#     try:
#         file = open('cache', 'rb')
#         _cache = pickle.load(file)
#         for k, v in _cache:
#             if 'ttl' in v:
#


# UDP server
cache = read_cache()
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((LOCAL_HOST, PORT))
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

while True:                                                     # listening infinite loop
    req, address = server.recvfrom(2048)                        # 512?
    parsed = dnslib.DNSRecord.parse(req)

    if cache.get((parsed.questions[0].qname, parsed.questions[0].qtype)):
        print(f'Using cached response for {parsed.questions[0].qname}')
        _header = dnslib.DNSHeader(parsed.header.id, q=1, a=len(cache.get((parsed.questions[0].qname,
                                                                           parsed.questions[0].qtype))[0]))
        _answer = dnslib.DNSRecord(_header, parsed.questions, cache.get((parsed.questions[0].qname,
                                                                         parsed.questions[0].qtype))[0])
        server.sendto(_answer.pack(), address)
    else:
        try:
            # TODO: FORWARDER hardcoded for debugging reasons
            client.sendto(req, (FORWARDER_2, PORT))          # FORWARDER needs to be changed to set_forwarding_address()
            dns_answer, z = client.recvfrom(2048)            # получаем ответ от сервера (DNS-пакет)
            dns_answer_parsed = dnslib.DNSRecord.parse(dns_answer)      # парсим его с помощью dnslib.DNSRecord
            cache[(dns_answer_parsed.questions[0].qname,                # заносим в кэш, организованный как хэш-таблица
                   dns_answer_parsed.questions[0].qtype)] = dns_answer_parsed.rr, time.time()
            if dns_answer_parsed.auth:
                cache[(dns_answer_parsed.questions[0].qname,
                       dns_answer_parsed.questions[0].qtype)] = dns_answer_parsed.rr, time.time()

            for extra_info in dns_answer_parsed.ar:
                cache[(extra_info.rname, extra_info.rtype)] = [extra_info], time.time()     # сохранение дополнительной
                                                                                            # информации из ответа

            write_cache(cache)
            print(cache)
            header = dnslib.DNSHeader(parsed.header.id, q=1,
                                      a=len(cache.get((parsed.questions[0].qname,
                                                       parsed.questions[0].qtype))[0]))
            _answer = dnslib.DNSRecord(header, parsed.questions,
                                       cache.get((parsed.questions[0].qname,
                                                  parsed.questions[0].qtype))[0])
            server.sendto(_answer.pack(), address)
        except Exception as ex:
            print(ex)

# TODO: removing entries from cache according to TTL expiry
