# -*- coding: utf-8 -*-
"""
This file is the main server script for the PeerChat application.
It is responsible for handling incoming connections, and managing
chat sessions between clients.
"""

__author__ = 'Oldmacintosh'
__version__ = ['v1.1.0', 'v1.1.1']
__date__ = 'September 2024'
__PROJECT__ = 'PeerChat'
__DEBUG__ = False

import datetime
import logging
import socket
import threading
from dependencies.modules.database import Database
from dependencies.modules.communicator import send, receive

# The allowed characters for the username except alphanumeric
ALLOWED_CHARS = '_@ '

SERVER: str = ''
PORT: int = 8080

# Create the main socket for the server for listening to
# incoming clients
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((SERVER, PORT))
server.listen()
server.settimeout(1)

# A dictionary to store the active clients with their id as the key
clients: dict[int, socket.socket] = {}

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s')
Logger = logging.getLogger()
Logger.setLevel(logging.INFO)


def handle_client(client: socket.socket, address: tuple[str, int]) -> None:
    """
    This function is responsible for handling the client connection.
    It authenticates the client, and allows the client to create
    chat sessions, send messages, and change username.
    :param client: The client socket object
    :param address: The address of the client
    """
    # Create a database object to interact with the database
    database: Database = Database()
    # id of the user in the database
    _id: int | None = None
    # flag to check if the user public key is different from the one in
    # the database
    key_changed: bool = False
    registered: bool = False
    try:
        ip = address[0]
        mac = receive(client)
        user = database.get_user(mac)
        key = receive(client)

        if not user:
            send('unregistered', client)
            username = get_username(client, database)
            user = database.add_user(ip, mac, username, key)
            Logger.info('main: User registered(%s, %s)', username, ip)
        else:
            registered = True
            send('registered', client)
            if key != user[4]:
                key_changed = True
                database.change_key(user[0], key)
                user = database.get_user(mac)
            username = user[3]
            Logger.info('main: User connected(%s, %s)', username, ip)
            if key_changed:
                Logger.info('main: User key changed(%s, %s)', username, ip)

        _id = user[0]
        send((_id, username), client)

        # Send user chats to the client if the user is registered
        if registered:
            for chat in database.get_user_chats(_id):
                send(chat, client)
                # Send the change key command to the peer client if
                # the user key has changed and the peer client is
                # online
                if key_changed and chat['peer_id'] in clients and chat['peer_id'] != _id:
                    send({'command': 'change_key', 'peer_id': _id, 'peer_key': user[4]},
                         clients[chat['peer_id']])
            send('sync complete', client)

        # Add the client to the active clients dictionary
        clients[_id] = client

        while True:
            data = receive(client)

            if data['command'] == 'create_chat':
                create_chat(client, _id, data, database)

            elif data['command'] == 'change_username':
                send(data, client)
                # Delete the client from the dictionary to prevent
                # sending messages while the username is being changed
                del clients[_id]
                username = get_username(client, database)
                database.change_username(_id, username)
                clients[_id] = client
                Logger.info('main: Username changed(%s, %s)', username, user[3])
                user = database.get_user_id(_id)

            elif data['command'] == 'search_peer':
                send({
                    'command': 'search_peer',
                    'users': database.get_users(data['username'])
                }, client)

            elif data['command'] == 'send_message':
                send_message(_id, data, database)

            elif data['command'] == 'read_messages':
                database.read_messages(data['chat_id'])
    except (ConnectionResetError, ConnectionAbortedError):
        if _id in clients:
            del clients[_id]
        client.close()
        Logger.info('main: Connection closed(%s)', address)

    except Exception as _error:
        Logger.exception(_error)


def create_chat(client: socket.socket, _id: int, data: dict, database: Database) -> None:
    """
    This function is responsible for creating a chat session between
    two users.
    :param client: The client socket object of the first user
    :param _id: The id of the first user in the database
    :param data: The data received from the client regarding the
                 second user
    :param database: The database object to interact with the database
    """
    chat_id = database.create_chat(_id, data['peer_id'])
    user = database.get_user_id(_id)
    peer = database.get_user_id(data['peer_id'])
    data = {
        'command': 'create_chat',
        'chat_id': chat_id
    }
    _clients = [clients[_id]]
    # Send the create chat command to the peer client if the peer
    # client is online and also to the user client
    if peer[0] in clients and peer[0] != _id:
        _clients.append(clients[peer[0]])
    for _client in _clients:
        if _client:
            if _client == client:
                data['is_user_1'] = True
                data['peer_id'] = peer[0]
                data['peer_username'] = peer[3]
                data['peer_key'] = peer[4]
            else:
                data['is_user_1'] = False
                data['peer_id'] = _id
                data['peer_username'] = user[3]
                data['peer_key'] = user[4]
            send(data, _client)
    Logger.info('main: Chat created(%s, %s)', user[3], peer[3])


def send_message(_id: int, data: dict, database: Database) -> None:
    """
    This function is responsible for sending messages between two
    users.
    :param _id: The id of the user sending the message
    :param data: The data received from the client regarding the
                 message
    :param database: The database object to interact with the database
    """
    chat_id = data['chat_id']
    message = data['message']
    dt = datetime.datetime.now(datetime.timezone.utc).strftime('%d-%m-%Y %H:%M')
    self_chat = _id == data['peer_id']
    msg_id = database.add_message(chat_id, _id, message, dt, not self_chat)
    # Send the message to the peer client if the peer client is online
    if data['peer_id'] in clients and not self_chat:
        send({
            'command': 'receive_message',
            'chat_id': chat_id,
            'message': database.get_message(chat_id, msg_id),
        }, clients[data['peer_id']])


def get_username(client: socket.socket, database: Database) -> str:
    """
    This function is responsible for getting the username from the
    client and validating it.
    :param client: The client socket object
    :param database: The database object to interact with the database
    :return: The username of the client
    """
    while True:
        username = receive(client)
        if not ''.join([char for char in username if char not in ALLOWED_CHARS]).isalnum():
            send('invalid username', client)
            continue
        if database.validate_username(username):
            send('username accepted', client)
            return username
        send('This username is already taken', client)


def listen(_server: socket.socket) -> tuple[socket.socket, tuple[str, int]] | None:
    """
    This function is responsible for listening for incoming client
    connections and accepting them if they are valid.
    :param _server: The server socket object
    :return: A tuple containing the client socket object and the
             address of the client
    """
    _connection: tuple[socket.socket, tuple[str, int]] | None = None
    try:
        _connection = _server.accept()
        _connection[0].settimeout(30)
        # Check if the client is a valid client if debug mode is off
        if (_connection[0].recv(64).decode() in [f'{__PROJECT__}_{version}'
                                                 for version in __version__] or __DEBUG__):
            _connection[0].settimeout(None)
        else:
            raise ConnectionResetError
        send('Connected', _connection[0])
        return _connection
    except (UnicodeDecodeError, ConnectionResetError, ConnectionAbortedError, socket.timeout):
        if _connection:
            _connection[0].close()
        return None


if __name__ == '__main__':
    Logger.info('main: Server is listening for connections...')
    try:
        while True:
            connection = listen(server)
            if connection:
                threading.Thread(target=handle_client,
                                 args=(connection[0], connection[1])).start()
                Logger.info('main: Connection accepted(%s)', connection[1])
    except KeyboardInterrupt:
        pass

    except Exception as error:
        Logger.exception(error)

    finally:
        server.close()
        Logger.info('main: Server shutdown successful.')
