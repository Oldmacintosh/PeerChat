# -*- coding: utf-8 -*-
"""
Module containing the Database class for interacting with the
SQLite database.
"""

import os
import sqlite3


class Database:
    """
    Class for interacting with the SQLite database.
    It contains functions for adding users, creating chats, etc. to the
    database.
    """

    connection: sqlite3.Connection
    cursor: sqlite3.Cursor

    def __init__(self, path: str = os.path.join(os.path.dirname(__file__), 'data', 'database.db')):
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.cursor = self.connection.cursor()

        # Create the necessary tables if they don't exist
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT,
                mac TEXT,
                username TEXT UNIQUE,
                key TEXT,
                UNIQUE (ip, mac)
            );
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                chat_id TEXT PRIMARY KEY,
                user_1 INTEGER,
                user_2 INTEGER,
                FOREIGN KEY (user_1) REFERENCES users(user_id),
                FOREIGN KEY (user_2) REFERENCES users(user_id)
            );
        ''')

    def add_user(self, ip: str, mac: str, username: str, key: str) -> list:
        """
        Add a user to the database.
        :param ip: The IP address of the user
        :param mac: The MAC address of the user
        :param username: The username of the user
        :param key: The public key of the user
        :return: A list containing the user details
        """
        self.cursor.execute('INSERT INTO users (ip, mac, username, key) VALUES (?, ?, ?, ?)',
                            (ip, mac, username, key))
        self.connection.commit()
        return self.get_user(ip, mac)

    def create_chat(self, user_id_1: int, user_id_2: int) -> str:
        """
        Create a chat between two users.
        :param user_id_1: The id of the first user
        :param user_id_2: The id of the second user
        :return: The chat id of the created chat
        """
        chat_id = f'chat_{user_id_1}_{user_id_2}'
        self.cursor.execute('INSERT INTO chats (chat_id, user_1, user_2) VALUES (?, ?, ?)',
                            (chat_id, user_id_1, user_id_2))
        self.connection.commit()

        chat_table_sql = f'''
            CREATE TABLE IF NOT EXISTS {chat_id} (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                message TEXT,
                dt TEXT,
                unread bool,
                FOREIGN KEY (sender_id) REFERENCES users(user_id),
                CHECK (sender_id = {user_id_1} OR sender_id = {user_id_2})
        );
        '''
        self.cursor.execute(chat_table_sql)
        self.connection.commit()
        return chat_id

    def add_message(self, chat_id: str, sender_id: int,
                    message: str, dt: str, unread: bool) -> int:
        """
        Add a message to a chat.
        :param chat_id: The id of the chat
        :param sender_id: The id of the sender
        :param message: The message to send
        :param dt: The date and time of the message
        :param unread: Whether the message is unread
        :return: The id of the added message
        """
        self.cursor.execute(
            f'INSERT INTO {chat_id} (sender_id, message, dt, unread) VALUES (?, ?, ?, ?)',
            (sender_id, message, dt, unread))
        self.connection.commit()
        return self.cursor.lastrowid

    def get_message(self, chat_id: str, message_id: int) -> list:
        """
        Get a message from a chat.
        :param chat_id: The id of the chat
        :param message_id: The id of the message
        :return: A list containing the message and its details
        """
        self.cursor.execute(f'SELECT * FROM {chat_id} WHERE message_id = ?', (message_id,))
        return self.cursor.fetchone()

    def get_user(self, ip: str, mac: str) -> list | None:
        """
        Get a user from the database.
        :param ip: The IP address of the user
        :param mac: The MAC address of the user
        :return: A list containing the user details or None if the user
                 is not found
        """
        self.cursor.execute('SELECT * FROM users WHERE ip = ? AND mac = ?', (ip, mac))
        return self.cursor.fetchone()

    def get_user_id(self, _id: int) -> list:
        """
        Get a user from the database using the user id.
        :param _id: The id of the user
        :return: A list containing the user details
        """
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (_id,))
        return self.cursor.fetchone()

    def get_users(self, username: str) -> list:
        """
        Get a list of users from the database.
        :param username: The username of the user
        :return: A list containing the user details of the users with
                 a matching username
        """
        self.cursor.execute('SELECT * FROM users WHERE username LIKE ?', (f'%{username}%',))
        return self.cursor.fetchall()

    def get_user_chats(self, user_id: int) -> list:
        """
        Get a list of chats of a user.
        :param user_id: The id of the user
        :return: A list of chats of the user
        """
        self.cursor.execute('SELECT * FROM chats WHERE user_1 = ? OR user_2 = ?',
                            (user_id, user_id))
        _chats = self.cursor.fetchall()
        chats = []
        # Get the details of each chat the user is in
        for chat in _chats:
            chat_id = chat[0]
            is_user_1 = chat[1] == user_id
            peer = self.get_user_id(chat[2] if is_user_1 else chat[1])
            # Get the last 50 messages of the chat
            self.cursor.execute(f'SELECT * FROM {chat_id} ORDER BY message_id DESC LIMIT 50')
            messages = self.cursor.fetchall()[::-1]
            chats.append({
                'command': 'create_chat',
                'chat_id': chat_id,
                'is_user_1': is_user_1,
                'peer_id': peer[0],
                'peer_username': peer[3],
                'peer_key': peer[4],
                'messages': messages})
        return chats

    def validate_username(self, username: str) -> bool:
        """
        Validate a username to check if it is unique.
        :param username: The username to validate
        :return: True if the username is unique, False otherwise
        """
        self.cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        return self.cursor.fetchone() is None

    def change_username(self, user_id: int, username: str) -> None:
        """
        Change the username of a user.
        :param user_id: The id of the user
        :param username: The new username of the user
        """
        self.cursor.execute('UPDATE users SET username = ? WHERE user_id = ?',
                            (username, user_id))
        self.connection.commit()

    def change_key(self, user_id: int, key: str) -> None:
        """
        Change the key of a user.
        :param user_id: The id of the user
        :param key: The new key of the user
        """
        self.cursor.execute('UPDATE users SET key = ? WHERE user_id = ?',
                            (key, user_id))
        self.connection.commit()

    def read_messages(self, chat_id: str) -> None:
        """
        Mark all messages in a chat as read.
        :param chat_id: The id of the chat
        """
        self.cursor.execute(f'UPDATE {chat_id} SET unread = 0 WHERE unread = 1')
        self.connection.commit()
