# -*- coding: utf-8 -*-
"""
This module contains the functions for sending and receiving data
between two sockets.
"""

import pickle
import socket
from typing import Any

HEADER: int = 64
ENCODING: str = 'utf-8'


def send(data: Any, connection: socket.socket):
    """
    Sends data to the given connection. The data is first pickled
    and then sent.
    :param data: The data to send.
    :param connection: The connection to send the data to.
    """
    data = pickle.dumps(data)
    data_length = len(data)
    length_header = str(data_length).encode(ENCODING)
    length_header += b' ' * (HEADER - len(length_header))

    # Send the length of the data first
    connection.send(length_header)

    # Send the actual data
    connection.send(data)


def _recv(connection: socket.socket, *args, **kwargs) -> bytes:
    data = connection.recv(*args, **kwargs)
    if not data:
        raise ConnectionResetError("The connection was closed by the remote host.")
    return data


def receive(connection: socket.socket) -> Any:
    """
    Receives data from the given connection.
    :param connection: The connection to receive the data from.
    :return: The unpickled data received from the connection.
    :raises ConnectionResetError: If the connection is closed.
    """
    # Receive the length of the data first
    length_header = _recv(connection, HEADER).decode(ENCODING).strip()
    data_length = int(length_header)

    # Receive the actual data
    data = b''
    while len(data) < data_length:
        data += _recv(connection, data_length - len(data))

    return pickle.loads(data)
