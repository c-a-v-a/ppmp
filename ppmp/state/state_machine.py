"""Module for managing the peer-to-peer connection state machine.

This module contains the StateMachine class, which handles the lifecycle of
the app.
"""

import asyncio
import json
import logging
import time
from typing import Any

from ..cli import interface as cli
from ..crypto import cipher as cipher
from ..crypto import handshake as handshake
from ..crypto import identity as identity
from ..data import (
    AckFrame,
    ByeFrame,
    ErrorFrame,
    Frame,
    FrameType,
    HelloFrame,
    MessageFrame,
    PingFrame,
    PongFrame,
)
from ..network import connection as network
from .util import parse_incoming_frame

logger = logging.getLogger(__name__)


class StateMachine:
    """Manages the state, network lifecycles, and E2EE session for a peer connection."""

    def __init__(self, startup_config: cli.StartupConfig):
        """Initializes the StateMachine with necessary configs and protocol state variables.

        Args:
            startup_config: Configuration properties container including port, host, and mode.
        """

        self.config = startup_config

        self.my_identity_priv = identity.generate_identity()
        self.my_id = identity.get_public_key_b64(self.my_identity_priv)

        self.my_dh_priv = handshake.generate_dh_keypair()
        self.session_key = None
        self.peer_id = None

        self.msg_id_counter = 0
        self.last_activity = time.time()

        self.outgoing_queue = asyncio.Queue()
        self.exit_event = asyncio.Event()
        self.conn = None

    async def start(self):
        """Starts the state machine loop acting either as a Listener or a Caller server.

        Raises:
            network.NetworkError: If connection or handshake initialization fails fundamentally.
        """

        if self.config.mode == cli.PeerMode.LISTENER:
            cli.print_info(f"Starting server on port {self.config.port}...")
            server = network.PPMPServer(
                on_connect=self._handle_incoming_connection,
                port=self.config.port,
            )

            await server.start()
            await self.exit_event.wait()
            await server.stop()

        elif self.config.mode == cli.PeerMode.CALLER:
            cli.print_info(
                f"Connecting to {self.config.host}:{self.config.port}..."
            )

            try:
                conn = await network.connect_with_retry(
                    self.config.host, self.config.port
                )

                await self._run_session(conn)
            except network.NetworkError as e:
                cli.print_error(f"Failed to establish connection: {e}")
                self.exit_event.set()

    async def _handle_incoming_connection(self, conn: network.PPMPConnection):
        """Accepts or rejects an inbound socket connection requests.

        Args:
            conn: The active network connection instance targeting this peer.
        """

        if self.conn and not self.conn.is_closed():
            logger.warning("Connection rejected - an active session already exists.")

            return
        await self._run_session(conn)

    async def _run_session(self, conn: network.PPMPConnection):
        """Establishes security keys and manages lifetimes of async communication tasks.

        Args:
            conn: The validated, opened network connection wrapper object.
        """

        self.conn = conn

        cli.print_status(
            f"Connected to {conn.remote_address[0]}:{conn.remote_address[1]}"
        )

        try:
            if not await self._perform_handshake():
                cli.print_error(
                    "Authentication error during Handshake! Disconnecting."
                )

                await self._send_error(
                    "ERR_AUTH_FAILED", "Handshake verification failed."
                )

                return

            input_task = asyncio.create_task(
                cli.input_loop(self.outgoing_queue, self.exit_event)
            )

            send_task = asyncio.create_task(self._network_send_loop())
            recv_task = asyncio.create_task(self._network_receive_loop())
            keepalive_task = asyncio.create_task(self._keepalive_loop())

            await self.exit_event.wait()

            cli.print_info("Closing session...")

            await self._send_bye()

            for task in [input_task, send_task, recv_task, keepalive_task]:
                task.cancel()

        except network.ConnectionLostError:
            cli.print_status("Connection was terminated by the remote peer.")
        except Exception as e:
            cli.print_error(f"A critical session exception occurred: {e}")
        finally:
            self.exit_event.set()
            await self.conn.close()

    async def _perform_handshake(self) -> bool:
        """Executes a authenticated Diffie-Hellman handshake step with the peer.

        Returns:
            True if signature checks pass and symmetric session keys generate; False otherwise.
        """

        my_dh_pub = handshake.get_dh_pubkey_b64(self.my_dh_priv)
        timestamp = str(int(time.time()))

        data_to_sign = f"{self.my_id}|{timestamp}|{my_dh_pub}".encode("utf-8")
        sig = identity.sign_data(self.my_identity_priv, data_to_sign)

        hello_frame = HelloFrame(
            frame_type=FrameType.HELLO,
            timestamp=timestamp,
            sender_id=self.my_id,
            dh_pubkey=my_dh_pub,
            sig=sig,
        )

        await self.conn.send_frame(hello_frame.to_json())

        raw_peer_frame = await self.conn.recv_frame()

        try:
            peer_frame = parse_incoming_frame(raw_peer_frame)
        except Exception:
            return False

        if not isinstance(peer_frame, HelloFrame):
            return False

        self.peer_id = peer_frame.sender_id
        peer_data_to_verify = f"{peer_frame.sender_id}|{peer_frame.timestamp}|{peer_frame.dh_pubkey}".encode(
            "utf-8"
        )

        is_valid = identity.verify_signature(
            peer_frame.sender_id, peer_data_to_verify, peer_frame.sig
        )

        if not is_valid:
            return False

        self.session_key = handshake.generate_session_key(
            self.my_dh_priv, peer_frame.dh_pubkey
        )

        cli.print_info("Encrypted E2EE channel successfully established.")

        return True

    async def _network_send_loop(self):
        """Monitors the outgoing UI queue, encrypting and sending messages continuously."""

        while not self.exit_event.is_set():
            text = await self.outgoing_queue.get()

            encrypted_payload = cipher.encrypt_message(self.session_key, text)

            self.msg_id_counter += 1

            msg_frame = MessageFrame(
                frame_type=FrameType.MSG,
                timestamp=str(int(time.time())),
                msg_id=str(self.msg_id_counter),
                sender_id=self.my_id,
                payload=encrypted_payload,
            )

            await self.conn.send_frame(msg_frame.to_json())

            self.last_activity = time.time()
            self.outgoing_queue.task_done()

    async def _network_receive_loop(self):
        """Asynchronously reads inbound raw frames and reacts based on frame categories."""

        while not self.exit_event.is_set():
            raw_frame = await self.conn.recv_frame()
            self.last_activity = time.time()

            try:
                frame = parse_incoming_frame(raw_frame)
            except Exception as e:
                await self._send_error("ERR_BAD_FORMAT", f"Invalid frame: {e}")
                continue

            match frame:
                case MessageFrame():
                    try:
                        decrypted_text = cipher.decrypt_message(
                            self.session_key, frame.payload
                        )
                        short_peer_name = self.peer_id[:10] + "..."

                        cli.print_message(short_peer_name, decrypted_text)
                        await self._send_ack(frame.msg_id)
                    except ValueError as e:
                        cli.print_error(f"Data integrity loss: {e}")
                        await self._send_error(
                            "ERR_AUTH_FAILED", "Decryption failed."
                        )

                case AckFrame():
                    pass

                case PingFrame():
                    await self._send_pong()

                case PongFrame():
                    pass

                case ByeFrame():
                    reason = getattr(frame, "reason", "none specified")

                    cli.print_info(
                        f"Peer closed the session. Reason: {reason}"
                    )
                    self.exit_event.set()

                case ErrorFrame():
                    cli.print_error(
                        f"Critical error from Peer [{frame.code}]: {frame.message}"
                    )
                    self.exit_event.set()

    async def _keepalive_loop(self):
        """Periodically pings the peer if there is no network frame activity for 30 seconds."""

        while not self.exit_event.is_set():
            await asyncio.sleep(5)
            if time.time() - self.last_activity > 30.0:
                ping_frame = PingFrame(
                    frame_type=FrameType.PING, timestamp=str(int(time.time()))
                )

                try:
                    await self.conn.send_frame(ping_frame.to_json())

                    self.last_activity = time.time()
                except network.ConnectionLostError:
                    break

    async def _send_ack(self, ack_id: str):
        """Constructs and delivers an acknowledgment message tracking received messages.

        Args:
            ack_id: The identifier string matching the verified inbound MessageFrame ID.
        """

        ack = AckFrame(
            frame_type=FrameType.ACK,
            timestamp=str(int(time.time())),
            ack_id=ack_id,
        )
        await self.conn.send_frame(ack.to_json())

    async def _send_pong(self):
        """Responds to an inbound Ping keepalive check."""

        pong = PongFrame(
            frame_type=FrameType.PONG, timestamp=str(int(time.time()))
        )

        await self.conn.send_frame(pong.to_json())

    async def _send_bye(self):
        """Signs and transmits a session termination payload to the peer frame endpoint."""

        bye_data = f"{self.my_id}|BYE".encode("utf-8")
        sig = identity.sign_data(self.my_identity_priv, bye_data)
        bye = ByeFrame(
            frame_type=FrameType.BYE,
            timestamp=str(int(time.time())),
            reason="User executed /exit command",
            sig=sig,
        )

        try:
            await self.conn.send_frame(bye.to_json())
        except network.ConnectionLostError:
            pass

    async def _send_error(self, code: str, msg: str):
        """Constructs and transmits an unencrypted descriptive protocol error frame.

        Args:
            code: Internal categorical error string flag identifier.
            msg: Descriptive literal message explaining context to the peer.
        """

        err = ErrorFrame(
            frame_type=FrameType.ERROR,
            timestamp=str(int(time.time())),
            code=code,
            message=msg,
        )
        
        try:
            await self.conn.send_frame(err.to_json())
        except network.ConnectionLostError:
            pass