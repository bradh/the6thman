#!/usr/bin/env python3

import asyncio

from configparser import ConfigParser, SectionProxy
from typing import Union
import xml.etree.ElementTree as ET
import time

import takproto

import pytak

import multiprocessing as mp

state = dict()

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

    async def generate_cot(self, cvEvent):
        root = ET.Element("event")
        root.set("version", "2.0")
        root.set("type", "a-s-G")  # insert your type of marker
        root.set("uid", "6thMan")
        root.set("how", "m-g")
        root.set("time", pytak.cot_time())
        root.set("start", pytak.cot_time())
        root.set(
            "stale", pytak.cot_time(20)
        )  # time difference in seconds from 'start' when stale initiates

        pt_attr = {
            "lat": "-27.456604",
            "lon": "153.037484",
            "hae": "0",
            "ce": "10",
            "le": "10",
        }

        ET.SubElement(root, "point", attrib=pt_attr)

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
                await self.generate_cot(cot.cotEvent)
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
    config["mycottool"] = {"COT_URL": "udp://239.2.3.1:6969"}
    config = config["mycottool"]

    # Initializes worker queues and tasks.
    clitool = pytak.CLITool(config)
    await my_setup(clitool)
    
    # Start all tasks.
    await clitool.run()
    


if __name__ == "__main__":
    asyncio.run(main())