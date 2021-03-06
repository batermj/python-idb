#!/usr/bin/env python
'''
Parse and display license information from an IDA Pro database.

author: Willi Ballenthin
email: willi.ballenthin@gmail.com
'''
import sys
import struct
import logging
import datetime

import argparse

import idb
import idb.netnode


logger = logging.getLogger(__name__)


def is_encrypted(buf):
    return buf.find(b'\x00' * 4) >= 0x80


HEXRAYS_PUBKEY = 0x93AF7A8E3A6EB93D1B4D1FB7EC29299D2BC8F3CE5F84BFE88E47DDBDD5550C3CE3D2B16A2E2FBD0FBD919E8038BB05752EC92DD1498CB283AA087A93184F1DD9DD5D5DF7857322DFCD70890F814B58448071BBABB0FC8A7868B62EB29CC2664C8FE61DFBC5DB0EE8BF6ECF0B65250514576C4384582211896E5478F95C42FDED


def decrypt(buf):
    '''
    decrypt the given 1024-bit blob using Hex-Ray's public key.

    i'm not sure from where this public key originally came.
    the algorithm is derived from here:
        https://github.com/nlitsme/pyidbutil/blob/87cb3235a462774eedfafca00f67c3ce01eeb326/idbtool.py#L43

    Args:
      buf (bytes): at least 0x80 bytes, of which the first 1024 bits will be decrypted.

    Returns:
      bytes: 0x80 bytes of decrypted data.
    '''
    enc = int.from_bytes(buf[:0x80], 'little')
    dec = pow(enc, 0x13, HEXRAYS_PUBKEY)
    return dec.to_bytes(0x80, 'big')


def parse_user_data(buf):
    '''
    parse a decrypted user blob into a structured dictionary.

    Args:
      buf (bytes): exactly 0x80 bytes of plaintext data.

    Returns:
      Dict[str, Any]: a dictionary with the following values:
        - ts1 (datetime.datetime): timestamp in UTC of something. database creation?
        - ts2 (datetime.datetime): timestamp in UTC of something. sometimes zero.
        - id (str): the ID of the license.
        - name (str): the name of the user and organization that owns the license.
    '''
    if len(buf) != 0x80:
        raise ValueError('invalid user blob.')

    version = struct.unpack_from('<H', buf, 0x3)
    if version == 0:
        raise NotImplementedError('user blob version not supported.')

    ts1, _, ts2 = struct.unpack_from('<III', buf, 0x11)
    id = "%02X-%02X%02X-%02X%02X-%02X" % struct.unpack_from("6B", buf, 0x1D)
    name = buf[0x23:buf.find(b'\x00', 0x23)].decode('utf-8')

    return {
        # unknown if these are in UTC or not. right now, assuming so.
        'ts1': datetime.datetime.utcfromtimestamp(ts1),
        'ts2': datetime.datetime.utcfromtimestamp(ts2),
        'id': id,
        'name': name,
    }


def get_userdata(netnode):
    '''
    fetch, decrypt, and parse the user data from the given netnode.

    Args:
      netnode (ida_netnode.Netnode): the netnode containing the user data.

    Returns:
      dict[str, Any]: see `parse_user_data`.
    '''
    userdata = netnode.supval(0x0)

    if is_encrypted(userdata):
        userdata = decrypt(userdata)
    else:
        userdata = userdata[:0x80]

    return parse_user_data(userdata)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Parse and display license information from an IDA Pro database.")
    parser.add_argument("idbpath", type=str,
                        help="Path to input idb file")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Disable all output but errors")
    args = parser.parse_args(args=argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger().setLevel(logging.ERROR)
    else:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger().setLevel(logging.INFO)

    with idb.from_file(args.idbpath) as db:
        api = idb.IDAPython(db)
        data = get_userdata(api.ida_netnode.netnode('$ original user'))

        print('user: %s' % data['name'])
        print('id:   %s' % data['id'])
        print('ts1:  %s' % data['ts1'].isoformat(' ') + 'Z')
        print('ts2:  %s' % data['ts2'].isoformat(' ') + 'Z')

    return 0


if __name__ == "__main__":
    sys.exit(main())
