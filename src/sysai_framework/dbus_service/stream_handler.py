"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: stream_handler.py
Desc: Stream handling for D-Bus chat completion streaming
Date: 2025-11-18
Author: Liu Mingran
"""

import logging
import threading
import time
import json
import asyncio
from typing import Dict, Any, Generator

logger = logging.getLogger(__name__)


class StreamHandler:
    """
    Handles streaming responses for D-Bus chat completion streaming.
    Manages background threads for stream processing and signal emission.
    """

    def __init__(self, service_object):
        """
        Initialize stream handler.

        Args:
            service_object: ChatServiceObject instance for signal emission
        """
        self.service_object = service_object
        self.active_streams = {}  # request_id -> thread

    def start_stream(self, request_id: str, request: Dict):
        """
        Start processing a streaming request in background.

        Args:
            request_id: Unique request identifier
            request: Request parameters
        """
        if request_id in self.active_streams:
            logger.warning(f"Stream {request_id} already active")
            return

        # Start streaming in a background thread
        thread = threading.Thread(
            target=self._process_stream,
            args=(request_id, request),
            daemon=True
        )
        self.active_streams[request_id] = thread
        thread.start()

        logger.info(f"Started stream processing for {request_id}")

    def _process_stream(self, request_id: str, request: Dict):
        """
        Process streaming request and emit D-Bus signals.

        Args:
            request_id: Request ID
            request: Request parameters
        """
        try:
            model_router = self.service_object.model_router
            if not model_router:
                raise Exception("Model router not available")
            messages = request.get("messages", [])
            model = request.get("model")
            temperature = request.get("temperature", 0.7)
            max_tokens = request.get("max_tokens", 1000)
            top_p = request.get("top_p", 1.0)
            stream_generator = model_router.route_chat_completion(
                model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
                top_p=top_p, stream=True)
            total_content = ""
            chunk_index = 0
            async def consume_stream():
                nonlocal total_content, chunk_index
                try:
                    async for chunk_data in stream_generator:
                        try:
                            if isinstance(chunk_data, str):
                                if chunk_data.startswith("data: "):
                                    cs = chunk_data[6:].strip()
                                    if cs == "[DONE]":
                                        break
                                    chunk_dict = json.loads(cs)
                                else:
                                    continue
                            else:
                                chunk_dict = chunk_data
                            if "choices" in chunk_dict and chunk_dict["choices"]:
                                c = chunk_dict["choices"][0]
                                if "delta" in c and "content" in c["delta"]:
                                    cont = c["delta"]["content"]
                                    if cont:
                                        total_content += cont
                            from .type_converter import response_to_dbus
                            dbus_chunk = response_to_dbus(chunk_dict)
                            self.service_object.StreamChunk(request_id, dbus_chunk)
                            chunk_index += 1
                        except json.JSONDecodeError as e:
                            logger.error("Failed to parse chunk: %s", e)
                            continue
                        except Exception as e:
                            logger.error("Error processing chunk: %s", e)
                            continue
                except Exception as e:
                    logger.error("Async stream error for %s: %s", request_id, e)
                    try:
                        from .type_converter import response_to_dbus
                        self.service_object.StreamChunk(request_id, response_to_dbus({"object": "chat.completion.chunk", "choices": [{"delta": {}, "finish_reason": "error"}]}))
                        self.service_object.StreamDone(request_id, response_to_dbus({}))
                    except Exception:
                        pass
            try:
                asyncio.run(consume_stream())
            except Exception as e:
                logger.error("Stream processing error for %s: %s", request_id, e)
            usage = {"prompt_tokens": 0, "completion_tokens": len(total_content.split()) if total_content else 0, "total_tokens": len(total_content.split()) if total_content else 0}
            from .type_converter import response_to_dbus
            dbus_usage = response_to_dbus(usage)
            self.service_object.StreamDone(request_id, dbus_usage)
            logger.info("Stream %s completed, %s chunks", request_id, chunk_index)
        except Exception as e:
            logger.error("Stream processing error for %s: %s", request_id, e)
            try:
                from .type_converter import response_to_dbus
                self.service_object.StreamChunk(request_id, response_to_dbus({"object": "chat.completion.chunk", "choices": [{"delta": {}, "finish_reason": "error"}]}))
                self.service_object.StreamDone(request_id, response_to_dbus({}))
            except Exception:
                pass

        finally:
            # Clean up
            if request_id in self.active_streams:
                del self.active_streams[request_id]


