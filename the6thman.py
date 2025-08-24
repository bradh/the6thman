#!/usr/bin/env python3

import asyncio
import base64
import logging
import mimetypes
import json
import os
import requests

from configparser import ConfigParser, SectionProxy
from typing import Union
import xml.etree.ElementTree as ET

import pytak
# import takproto

import multiprocessing as mp

state = dict()

STALE_LENGTH = 5 # Time returned COTs should be valid for in seconds
USE_PROTO = True # True to send COTs in Protobuf, False to send COTs in XML

supportedMimeTypes = [
    'image/png', 'image/jpeg', 'image/jpg', 'image/gif'
]


def getMimeType(fileName):
    return mimetypes.guess_type(fileName)[0]


def isSupportedMimeType(mimeType):
    return mimeType in supportedMimeTypes


def extractFeaturesWithAI(buffer, originalMimeType):
    # fileSignature = buffer[:5].decode(errors='ignore')

    workingBuffer = buffer
    mimeType = originalMimeType

    # print(f"🖼️ Detected file (sig: {fileSignature})")
    mimeType = originalMimeType or 'image/png'

    base64Image = base64.b64encode(workingBuffer).decode('utf-8')

    payload = {
        "model": "gemma3:27b",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """
                        You are a visual analysis model focused on situational awareness.

                        Your tasks are to analyze the image and answer the following questions as simply and objectively as possible. 
                        Return a **single raw JSON object** with these exact keys:

                        {
                          "peopleCount": <integer>,
                          "hostiles": true/false,
                          "weaponsDetected": true/false,
                          "Hazards": true/false,
                          "rubble": true/false
                        }

                        Definitions:
                        - peopleCount: Number of distinct HUMAN people visible (ignore mannequins, posters, photos, statues).
                        - weaponsDetected: true if any weapons (guns, knives, explosives, etc.) are visible; false otherwise.
                        - hostiles: assume true if weapons present; false otherwise
                        - Hazards: true if hazards like fire, smoke, chemical spill, collapsed structures, or flood are visible.
                        - rubble: true if debris/rubble from destruction (collapsed walls, broken concrete, wreckage) is visible.

                        Rules:
                        - Always output ALL five keys.
                        - Use boolean true/false (lowercase).
                        - If unsure, lean towards false, except peopleCount which should be your best estimate.
                        - Output must be **only the JSON object** with no commentary, explanation, or formatting.
                        """.strip()
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mimeType};base64,{base64Image}"
                        }
                    }
                ]
            }
        ]
    }

    headers = {
        'Accept': '*/*',
        'Content-Type': 'application/json',
        'User-Agent': 'tp-ai-ocr-service',
        'Authorization': 'Bearer token-abc123'
    }

    response = requests.post(
        'http://10.1.1.198:11434/v1/chat/completions',
        json=payload,
        headers=headers
    )

    content = response.json()['choices'][0]['message']['content']

    return content

class ImageWorker():

    _logger = logging.getLogger(__name__)
    if not _logger.handlers:
        _logger.setLevel(pytak.LOG_LEVEL)
        _console_handler = logging.StreamHandler()
        _console_handler.setLevel(pytak.LOG_LEVEL)
        _console_handler.setFormatter(pytak.LOG_FORMAT)
        _logger.addHandler(_console_handler)
        _logger.propagate = False

    def __init__(self, cot_queue):
        self.output_queue = cot_queue


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
        await self.output_queue.put(cot)

    def _handleImageRecognitionUpload(self, fileBuffer, fileName):
        mimeType = getMimeType(fileName)
        # print(f"MIME Type: {mimeType}")

        if not isSupportedMimeType(mimeType):
            raise ValueError(f"Unsupported file type: {mimeType}")

        return extractFeaturesWithAI(fileBuffer, mimeType)

    async def _process_images(self):
        images_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images'))

        if not os.path.exists(images_dir):
            print(f"⚠️  Directory not found: {images_dir}")
            return

        print(f"📂 Scanning directory: {images_dir}")

        for file_name in os.listdir(images_dir):
            file_path = os.path.join(images_dir, file_name)

            if not os.path.isfile(file_path):
                continue

            mime_type = getMimeType(file_name)
            if not isSupportedMimeType(mime_type):
                print(f"⛔ Skipping unsupported file: {file_name} (MIME: {mime_type})")
                continue

            try:
                with open(file_path, 'rb') as f:
                    file_buffer = f.read()

                print(f"\n📨 Sending {file_name} to The 6th Man for Analysis...")
                result = self._handleImageRecognitionUpload(file_buffer, file_name)
                print(f"Situational analysis for {file_name}:\n{result}\n")
                # TODO: pull this from somewhere
                cvEvent = {
                    "lat": -29.0,
                    "lon": 153.0,
                    "hae": 26.0,
                    "ce": 999.99,
                    "le": 999999.99,
                }
                self.generate_cot(cvEvent, result)

            except Exception as e:
                print(f"💥 Failed to process {file_name}: {str(e)}")


    async def run_once(self) -> None:
        """Run this worker once."""
        await self._process_images()

    async def run(self, _=-1) -> None:
        """Run this worker."""
        self._logger.info("Running: %s", self.__class__.__name__)
        while True:
            await self.run_once()
            await asyncio.sleep(0.01)  # make sure other tasks have a chance to run

class SituationalUnderstander(pytak.CLITool):
    def __init__(self, config):
        super().__init__(config)

    async def setup(self) -> None:
        reader, writer = await pytak.protocol_factory(self.config)

        write_worker = pytak.TXWorker(self.tx_queue, self.config, writer)
        self.add_task(write_worker)

        read_worker = pytak.RXWorker(self.rx_queue, self.config, reader)
        self.add_task(read_worker)

        image_worker = ImageWorker(self.tx_queue)
        self.add_task(image_worker)

async def main():
    """
    The main definition of your program, sets config params and
    adds your serializer to the asyncio task list.
    """
    config = ConfigParser()
    config["tool"] = {"COT_URL": "udp://239.2.3.1:6969"} # default Multicast
    if USE_PROTO:
        config["tool"] = {"TAK_PROTO": 2} # 2 means mesh Protobuff
    config = config["tool"]

    # Initializes worker queues and tasks.
    clitool = SituationalUnderstander(config)
    await clitool.setup()
    
    # Start all tasks.
    await clitool.run()

if __name__ == "__main__":
    asyncio.run(main())