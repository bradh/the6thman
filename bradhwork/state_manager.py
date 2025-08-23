#!/usr/bin/env python3

import asyncio

import json
import os
import re

from configparser import ConfigParser, SectionProxy
from typing import Union
import xml.etree.ElementTree as ET
import time

import pytak
import takproto

import multiprocessing as mp

state = dict()

STALE_LENGTH = 5 # Time returned COTs should be valid for in seconds
USE_PROTO = True # True to send COTs in Protobuf, False to send COTs in XML

class MyRXWorker(pytak.RXWorker):

    tx_queue = None

    def __init__(
        self,
        queue: Union[asyncio.Queue, mp.Queue],
        config: Union[None, SectionProxy, dict],
        reader: asyncio.Protocol,
        tx_queue: Union[asyncio.Queue, mp.Queue],
    ) -> None:
        """Initialize a RXWorker instance."""
        super().__init__(queue, config, reader)
        self.tx_queue = tx_queue

    async def generate_test_cot(self, cvEvent):
        """Generate default COT for testing"""
        root = ET.Element("event")
        root.set("version", "2.0")
        root.set("type", "a-s-G")  # insert your type of marker
        root.set("uid", "team4test")
        root.set("how", "m-g")
        root.set("time", pytak.cot_time())
        root.set("start", pytak.cot_time())
        root.set(
            "stale", pytak.cot_time(STALE_LENGTH)
        )  # time difference in seconds from 'start' when stale initiates

        pt_attr = {
            "lat": "-27.456604",
            "lon": "153.037484",
            "hae": "0",
            "ce": "10",
            "le": "10",
        }

        ET.SubElement(root, "point", attrib=pt_attr)

        # self.tx_queue.put(pytak.gen_cot_xml("-27.456604", "153.037484", "10", "0", "10", "team4test", pytak.cot_time(20), "a-s-G"))

        cot = ET.tostring(root)
        await self.tx_queue.put(cot)

    async def generate_cot(self, cvEvent, features: str): # features is a JSON str
        """Return COT marker based on given features """
        root = ET.Element("event")
        if USE_PROTO:
            root.set("version", "2.0") # Switchover to Protobuf if v1.0

        features = features.loads() # Convert to JSON object

        # Switch marker type based on features
        if features["hostiles"]:
            root.set("type", "a-s-G")
        else:
            root.set("type", "a-s-A")

        # root.set("uid", "team4test")
        # root.set("how", "m-g")
        root.set("time", pytak.cot_time()) # Reset timestamp
        # root.set("start", pytak.cot_time())
        root.set("stale", cvEvent.time + STALE_LENGTH)
        
        # Append location and feature attributes to COT
        pt_attr = {
            "lat": cvEvent.lat,
            "lon": cvEvent.lon,
            "hae": cvEvent.hae,
            "ce": cvEvent.ce,
            "le": cvEvent.le,
            "peopleCount": str(features["peopleCount"]),
            "hostiles": str(features["hostiles"]),
            "weaponsDetected": str(features["weaponsDetected"]),
            "hazards": str(features["hazards"]),
            "rubble": str(features["rubble"])
        }

        ET.SubElement(root, "point", attrib=pt_attr)

        # Send out COT marker
        cot = ET.tostring(root)
        await self.tx_queue.put(cot)

    def cleanup(self):
        # print("doing cleanup")
        nowtime = time.time() * 1000
        to_remove = list()
        for entry in state:
            expiry = state[entry].staleTime
            if nowtime > expiry:
                to_remove.append(entry)
        for entry in to_remove:
            print("removing expired entry", entry)
            state.pop(entry)

    async def readcot(self):
        """Reads COT data"""
        if hasattr(self.reader, 'recv'):
            cot, src = await self.reader.recv()
        if cot.startswith(bytearray("<event version=", "utf8")):
            cot = bytearray("<?xml version='1.0' encoding='utf8'?>", "utf8") + cot
        tak_v1 = takproto.parse_proto(cot)
        if tak_v1 != -1:
            cot = tak_v1
        if cot is not None:
            # print("SRC: ", src)
            # print("COT: ", cot)
            print("event from: ", cot.cotEvent.uid)
            if cot.cotEvent.uid == "AutoCV1":
                await self.generate_test_cot(cot.cotEvent)
            else:    
                state[cot.cotEvent.uid] = cot.cotEvent
            pass
        else:
            # print("SRC: ", src)
            print("NO COT!")
            pass
        
        self.cleanup()

        return cot

async def my_setup(clitool) -> None:
    reader, writer = await pytak.protocol_factory(clitool.config)
    write_worker = pytak.TXWorker(clitool.tx_queue, clitool.config, writer)
    read_worker = MyRXWorker(clitool.rx_queue, clitool.config, reader, clitool.tx_queue)
    clitool.add_task(write_worker)
    clitool.add_task(read_worker)

async def main():
    """
    The main definition of your program, sets config params and
    adds your serializer to the asyncio task list.
    """
    config = ConfigParser()
    config["mycottool"] = {"COT_URL": "udp://239.2.3.1:6969"} # default Multicast
    if USE_PROTO:
        config["mycottool"] = {"TAK_PROTO": 2} # 2 means mesh Protobuff
    config = config["mycottool"]

    # Initializes worker queues and tasks.
    clitool = pytak.CLITool(config)
    await my_setup(clitool)
    
    # Start all tasks.
    await clitool.run()

if __name__ == "__main__":
    asyncio.run(main())