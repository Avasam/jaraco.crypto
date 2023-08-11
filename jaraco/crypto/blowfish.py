#
# blowfish.py
# Copyright (C) 2002 Michael Gilfix <mgilfix@eecs.tufts.edu>
#
# This module is open source; you can redistribute it and/or
# modify it under the terms of the GPL or Artistic License.
# These licenses are available at http://www.opensource.org
#
# This software must be used and distributed in accordance
# with the law. The author claims no liability for its
# misuse.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#

# This software was modified by Ivan Voras: CTR cipher mode of
# operation was added, together with testing and example code.
# These changes are (c) 2007./08. Ivan Voras <ivoras@gmail.com>
# These changes can be used, modified ad distributed under the
# GPL or Artistic License, the same as the original module.
# All disclaimers of warranty from the original module also
# apply to these changes.

"""
Blowfish Encryption

This module is a pure python implementation of Bruce Schneier's
encryption scheme 'Blowfish'. Blowish is a 16-round Feistel Network
cipher and offers substantial speed gains over DES.

The key is a string of length anywhere between 64 and 448 bits, or
equivalently 8 and 56 bytes. The encryption and decryption functions operate
on 64-bit blocks, or 8 byte strings.

Send questions, comments, bugs my way:
    Michael Gilfix <mgilfix@eecs.tufts.edu>

The module has been expanded to include CTR stream encryption/decryption
mode, built from the primitives from the orignal module. This change
did not alter any of the base Blowfish code from the original author.

The author of CTR changes is:
    Ivan Voras <ivoras@gmail.com>

Test usage:

>>> key = 'This is a test key'
>>> cipher = Blowfish (key)

test encryption

>>> xl = 123456
>>> xr = 654321

Plain text is (xl, xr)

>>> cl, cr = cipher.cipher(xl, xr, cipher.ENCRYPT)

Cipher text is (cl, cr)

>>> dl, dr = cipher.cipher(cl, cr, cipher.DECRYPT)

>>> (dl, dr) == (xl, xr)
True

Test block encrypt

>>> text = "testtext"

>>> crypted = cipher.encrypt(text.encode())
>>> crypted == text
False
>>> decrypted = cipher.decrypt(crypted).decode()
>>> decrypted
'testtext'

Test CTR encrypt

>>> text = "If the offer's shunned, you might as well be walking on the sun"

>>> cipher.initCTR()
>>> crypted = cipher.encryptCTR(text.encode())
>>> crypted == text
False
>>> cipher.initCTR()
>>> decrypted = cipher.decryptCTR(crypted).decode()
>>> decrypted
"If the offer's shunned, you might as well be walking on the sun"

"""

import struct

from importlib_resources import files
from more_itertools import chunked, flatten


__author__ = "Michael Gilfix <mgilfix@eecs.tufts.edu>"


class Blowfish:

    """Blowfish encryption Scheme

    This class implements the encryption and decryption
    functionality of the Blowfish cipher.

    Public functions:

        def __init__ (self, key)
            Creates an instance of blowfish using 'key'
            as the encryption key. Key is a string of
            length ranging from 8 to 56 bytes (64 to 448
            bits). Once the instance of the object is
            created, the key is no longer necessary.

        def encrypt (self, data):
            Encrypt an 8 byte (64-bit) block of text
            where 'data' is an 8 byte string. Returns an
            8-byte encrypted string.

        def decrypt (self, data):
            Decrypt an 8 byte (64-bit) encrypted block
            of text, where 'data' is the 8 byte encrypted
            string. Returns an 8-byte string of plaintext.

        def cipher (self, xl, xr, direction):
            Encrypts a 64-bit block of data where xl is
            the upper 32-bits and xr is the lower 32-bits.
            'direction' is the direction to apply the
            cipher, either ENCRYPT or DECRYPT constants.
            returns a tuple of either encrypted or decrypted
            data of the left half and right half of the
            64-bit block.

        def initCTR(self):
            Initializes CTR engine for encryption or decryption.

        def encryptCTR(self, data):
            Encrypts an arbitrary string and returns the
            encrypted string. The method can be called successively
            for multiple string blocks.

        def decryptCTR(self, data):
            Decrypts a string encrypted with encryptCTR() and
            returns the decrypted string.

    Private members:

        def __round_func(self, xl)
            Performs an obscuring function on the 32-bit
            block of data 'xl', which is the left half of
            the 64-bit block of data. Returns the 32-bit
            result as a long integer.

    """

    # Cipher directions
    ENCRYPT = 0
    DECRYPT = 1

    # For the __round_func
    modulus = 2**32

    def __init__(self, key):
        if not key or len(key) < 8 or len(key) > 56:
            raise RuntimeError(
                "Attempted to initialize Blowfish cipher with "
                "key of invalid length: %s" % len(key)
            )

        self.init_boxes()
        self.compute_boxes(key)
        self.initCTR()

    def init_boxes(self):
        self.p_boxes = self.load_boxes('p')[0]
        self.s_boxes = self.load_boxes('s')

    def load_boxes(self, type):
        buf = files().joinpath(f'{type}.bin').read_bytes()
        vals = flatten(struct.iter_unpack('!L', buf))
        return list(chunked(vals, 256))

    def compute_boxes(self, key):
        # Cycle through the p-boxes and round-robin XOR the
        # key with the p-boxes
        key_len = len(key)
        index = 0
        for i in range(len(self.p_boxes)):
            val = (
                (ord(key[index % key_len]) << 24)
                + (ord(key[(index + 1) % key_len]) << 16)
                + (ord(key[(index + 2) % key_len]) << 8)
                + ord(key[(index + 3) % key_len])
            )
            self.p_boxes[i] = self.p_boxes[i] ^ val
            index = index + 4

        # For the chaining process
        left, right = 0, 0

        # Begin chain replacing the p-boxes
        for i in range(0, len(self.p_boxes), 2):
            left, right = self.cipher(left, right, self.ENCRYPT)
            self.p_boxes[i] = left
            self.p_boxes[i + 1] = right

        # Chain replace the s-boxes
        for i in range(len(self.s_boxes)):
            for j in range(0, len(self.s_boxes[i]), 2):
                left, right = self.cipher(left, right, self.ENCRYPT)
                self.s_boxes[i][j] = left
                self.s_boxes[i][j + 1] = right

    def cipher(self, xl, xr, direction):
        """Encryption primitive"""
        if direction == self.ENCRYPT:
            for i in range(16):
                xl = xl ^ self.p_boxes[i]
                xr = self.__round_func(xl) ^ xr
                xl, xr = xr, xl
            xl, xr = xr, xl
            xr = xr ^ self.p_boxes[16]
            xl = xl ^ self.p_boxes[17]
        else:
            for i in range(17, 1, -1):
                xl = xl ^ self.p_boxes[i]
                xr = self.__round_func(xl) ^ xr
                xl, xr = xr, xl
            xl, xr = xr, xl
            xr = xr ^ self.p_boxes[1]
            xl = xl ^ self.p_boxes[0]
        return xl, xr

    def __round_func(self, xl):
        a = (xl & 0xFF000000) >> 24
        b = (xl & 0x00FF0000) >> 16
        c = (xl & 0x0000FF00) >> 8
        d = xl & 0x000000FF

        # Perform all ops as longs then and out the last 32-bits to
        # obtain the integer
        f = (self.s_boxes[0][a] + self.s_boxes[1][b]) % self.modulus
        f = f ^ self.s_boxes[2][c]
        f = f + self.s_boxes[3][d]
        f = (f % self.modulus) & 0xFFFFFFFF

        return f

    def encrypt(self, data):
        if not len(data) == 8:
            raise RuntimeError(
                "Attempted to encrypt data of invalid block length: %s" % len(data)
            )

        # Use big endianess since that's what everyone else uses
        xl = data[3] | (data[2] << 8) | (data[1] << 16) | (data[0] << 24)
        xr = data[7] | (data[6] << 8) | (data[5] << 16) | (data[4] << 24)

        cl, cr = self.cipher(xl, xr, self.ENCRYPT)
        chars = bytes(
            [
                (cl >> 24) & 0xFF,
                (cl >> 16) & 0xFF,
                (cl >> 8) & 0xFF,
                cl & 0xFF,
                (cr >> 24) & 0xFF,
                (cr >> 16) & 0xFF,
                (cr >> 8) & 0xFF,
                cr & 0xFF,
            ]
        )
        return chars

    def decrypt(self, data):
        if not len(data) == 8:
            raise RuntimeError(
                "Attempted to encrypt data of invalid block length: %s" % len(data)
            )

        # Use big endianess since that's what everyone else uses
        cl = data[3] | (data[2] << 8) | (data[1] << 16) | (data[0] << 24)
        cr = data[7] | (data[6] << 8) | (data[5] << 16) | (data[4] << 24)

        xl, xr = self.cipher(cl, cr, self.DECRYPT)
        chars = bytes(
            [
                (xl >> 24) & 0xFF,
                (xl >> 16) & 0xFF,
                (xl >> 8) & 0xFF,
                xl & 0xFF,
                (xr >> 24) & 0xFF,
                (xr >> 16) & 0xFF,
                (xr >> 8) & 0xFF,
                xr & 0xFF,
            ]
        )
        return chars

    def initCTR(self, iv=0):
        """Initializes CTR mode of the cypher"""
        assert struct.calcsize("Q") == self.blocksize()
        self.ctr_iv = iv
        self._calcCTRBUF()

    def _calcCTRBUF(self):
        """Calculates one block of CTR keystream"""
        # keystream block
        self.ctr_cks = self.encrypt(struct.pack("Q", self.ctr_iv))
        self.ctr_iv += 1
        self.ctr_pos = 0

    def _nextCTRByte(self):
        """Returns one byte of CTR keystream"""
        b = self.ctr_cks[self.ctr_pos]
        self.ctr_pos += 1
        if self.ctr_pos >= len(self.ctr_cks):
            self._calcCTRBUF()
        return b

    def encryptCTR(self, data):
        """
        Encrypts a buffer of data with CTR mode. Multiple successive buffers
        (belonging to the same logical stream of buffers) can be encrypted
        with this method one after the other without any intermediate work.
        """
        return bytes(ch ^ self._nextCTRByte() for ch in data)

    def decryptCTR(self, data):
        return self.encryptCTR(data)

    def blocksize(self):
        return 8

    def key_length(self):
        return 56

    def key_bits(self):
        return 56 * 8
