#!/usr/bin/env python3
"""Pretends to be mtx.py, but just executes shell commands and parses the output"""
import sh
import re
import json
import logging

logger = logging.getLogger(__name__)


class Changer(object):
    """Changer
    Represents a media changer device, and uses pyscsi to control it
    """

    def __init__(self, changer, do_status_update=False):
        self.status = {}
        self.ioslot = None
        self.changer = changer
        if do_status_update:
            self.update_status()

    def update_status(self):
        rawstatus = sh.mtx('-f', self.changer, "altres", "status").split("\n")
        mtxregexstring = "Storage Element (?P<number>[0-9]*)(?P<io> IMPORT/EXPORT|):"
        mtxregexstring += "(?P<state>Empty|Full).*"
        mtxregex = re.compile(mtxregexstring)
        for line in rawstatus:
            parseresult = mtxregex.match(line.strip())
            if parseresult is not None:
                status = parseresult.groupdict()

                # If this is our import/export slot, make note of it
                if status['io'] != "":
                    self.ioslot = status['number']

                # If this is our first run and we're just learning about the different elements
                elif status['number'] not in self.status:
                    self.status[status['number']] = {}
                    self.status[status['number']]['full'] = status['state'] == "Full"

                # If we previously believed this to be in a different state than it is, then our
                # information about what's in there is probably wrong
                elif status['state'] != self.status[status['number']]['state']:
                    self.status[status['number']] = {}
                    self.status[status['number']]['full'] = status['state'] == "Full"
        return self.status

    def load(self, slot=None):
        """
        Causes the changer to accept a disk and load it into the specified slot. If no slot is
        specified, it selects an empty slot (update_status() must have been run already). Returns
        the slot the disk was inserted into
        """
        if self.ioslot is None:
            raise NeverScannedError()
        if slot is None:
            for possible in self.status:
                if self.status['possible']['full'] is False:
                    slot = possible
            if slot is None:
                # No slots available to load stuff into
                raise NoSlotsAvailableError()
        sh.mtx('-f', self.changer, 'altres', 'eepos', 'transfer', self.ioslot, slot)
        self.status[slot]['full'] = True
        return slot

    def unload(self, slot):
        """
        Causes the changer to unload the disk from the specified slot and eject it from the changer
        """
        sh.mtx('-f', self.changer, 'altres', 'eepos', 'transfer', slot, self.ioslot)
        self.status[slot]['full'] = False

    def load_drive(self, slot, drive=0):
        """
        Loads the disk from the specified slot into the specified drive (default drive is 0)
        """
        try:
            sh.mtx('-f', self.changer, 'altres', 'load', slot, drive)
        except sh.ErrorReturnCode_1:
            raise DriveAlreadyLoaded()

    def get_status(self):
        return self.status


class IncorrectDeviceTypeError(Exception):
    def __str__(self):
        return "The device you selected is not a media changer"

class NeverScannedError(Exception):
    def __str__(self):
        err = "That operation can't be completed until you've run updateStatus() at least once"
        return err

class NoSlotsAvailableError(Exception):
    def __str__(self):
        return "No slots are available to load the disk into!"

class DriveAlreadyLoaded(Exception):
    def __str__(self):
        return "There is already a disk in the drive!"
