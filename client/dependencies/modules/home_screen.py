# -*- coding: utf-8 -*-
"""Module to handle the home screen for the application."""

import os
from datetime import datetime
import pickle
import socket
import multiprocessing
from tzlocal import get_localzone
import pytz
import main  # noqa
from dependencies.modules.thread_with_exc import ThreadWithExc  # noqa
from dependencies.modules.communicator import send, receive  # noqa
from dependencies.modules.raise_exc import raise_exception  # noqa
from kivy.metrics import Metrics
from kivy.clock import mainthread, Clock
from kivy.config import Config
from kivy.logger import Logger
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.properties import StringProperty
from kivymd.uix.screen import MDScreen
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogIcon,
    MDDialogHeadlineText,
    MDDialogSupportingText,
    MDDialogButtonContainer,
)

# Dictionary to store the width options of the message labels according
# to the length of the message
SIZES: dict[tuple, int] = {
    (0, 5): 80,
    (5, 10): 110,
    (10, 15): 140,
    (15, 20): 170,
    (20, 25): 200,
    (25, 30): 230,
    (30, 35): 260,
    (35, 40): 290,
    (40, 45): 320,
    (45, 50): 350,
}

NOTIFICATION_COLOR: list[int] = [1, 0.65, 0, 0.8]


def convert_utc_to_local(utc_time_str: str, local_timezone_str: str = str(get_localzone())) -> str:
    """
    Function to convert UTC time to local time.
    Time format: '%d-%m-%Y %H:%M'
    :param utc_time_str: The UTC time string
    :param local_timezone_str: The local timezone to convert to
    :return: The local time string
    """
    utc_time = datetime.strptime(utc_time_str, '%d-%m-%Y %H:%M')
    local_timezone = pytz.timezone(local_timezone_str)
    local_time = pytz.utc.localize(utc_time).astimezone(local_timezone)
    return local_time.strftime('%d-%m-%Y %H:%M')


class HomeScreen(MDScreen):
    """
    Class that handles the home screen of the application.
    It handles most of the functionalities of the application including
    sending and receiving messages, creating chats, changing usernames,
    etc.
    """

    SERVER: socket.socket | None = None

    # id and username of the user
    _id: int | None = None
    username: str | None = None

    # The current instance of the HomeScreen class that is being used
    current_instance = None

    chat_screens: dict = {}

    # The confirmation dialog for changing the username
    dialog: MDDialog | None = None

    self_chat_button: MDButton | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        HomeScreen.current_instance = self

    def on_pre_enter(self, *args) -> None:
        """Function to be executed before the screen is entered."""
        if self.self_chat_button:
            self.self_chat_button.clear_widgets()
            # Update the username of the self chat button as it may
            # have been changed
            username = f'{self.username} (You)'
            self.self_chat_button.add_widget(
                MDButtonText(text=username, theme_text_color='Custom', text_color='white'))

    def on_enter(self, *args) -> None:
        """Function to be executed when the screen is entered."""
        ThreadWithExc(target=self.listen).start()

    def on_release_search_peer(self) -> None:
        """
        Function to be executed when the search peer button
        is released.
        """

        # Set the screen manager to the AddUser screen
        if self.ids.search_peer_button.icon == 'account-search':
            self.ids.menu_title_label.text = 'Search'
            self.ids.search_peer_button.icon = 'chat'
            self.ids.sm.current = 'SearchPeer'

        # Set the screen manager to the Chats screen
        elif self.ids.search_peer_button.icon == 'chat':
            self.ids.menu_title_label.text = 'Chats'
            self.ids.search_peer_button.icon = 'account-search'
            self.ids.sm.current = 'Chats'

    def on_release_edit_username(self) -> None:
        """
        Function to be executed when the edit username button is
        released.
        """

        def on_release_change(*args) -> None:  # noqa
            """
            Function to be executed when the change button in the
            dialog is released.
            """
            self.dialog.dismiss()
            send({'command': 'change_username'}, self.SERVER)
            self.parent.current = 'UserName'

        def on_release_cancel(*args) -> None:  # noqa
            """
            Function to be executed when the cancel button in the
            dialog is released.
            """
            self.dialog.dismiss()

        # Create the dialog and the required buttons
        change_button = MDButton(
            MDButtonText(text='Yes', theme_text_color='Custom', text_color='white'), style='text')
        change_button.bind(on_release=on_release_change)

        cancel_button = MDButton(
            MDButtonText(text='No', theme_text_color='Custom', text_color='white'), style='text')
        cancel_button.bind(on_release=on_release_cancel)

        self.dialog = MDDialog(
            MDDialogIcon(icon='account-edit'),
            MDDialogHeadlineText(text='Change Username?'),
            MDDialogSupportingText(text=f'Your current username is {self.username}'),
            MDDialogButtonContainer(Widget(), cancel_button, change_button),
            state_press=0
        )

        self.dialog.open()

    def listen(self) -> None:
        """
        Function to listen for incoming messages and commands from the
        server and execute the required functions.
        """
        try:
            while True:
                data = receive(self.SERVER)

                if data['command'] == 'create_chat':
                    self.create_chat(data)

                elif data['command'] == 'receive_message':
                    chat_screen = self.chat_screens[data['chat_id']]
                    chat_screen.loading_messages = True
                    chat_screen.change_hint_text('Loading messages...', focus=None)
                    # Decrypt the message in a separate process and
                    # add it to saved chat
                    with multiprocessing.Pool(processes=1) as pool:
                        decrypted_message = pool.starmap(main.decrypt_message,
                                                         [(data['message'][2], main.key_dir)])
                    chat_screen.saved_chat.update(decrypted_message)
                    chat_screen.save_chat()
                    chat_screen.add_message(data['message'])
                    chat_screen.loading_messages = False
                    chat_screen.change_hint_text('Type a message', focus=None)
                    if self.ids.chat_sm.current == data['chat_id']:
                        # Mark the chat as read if the chat is currently
                        # open
                        send({'command': 'read_messages', 'chat_id': data['chat_id']},
                             HomeScreen.current_instance.SERVER)
                    else:
                        self.notify(data['chat_id'])

                elif data['command'] == 'search_peer':
                    self.ids.search_peer.add_peers(data['users'])

                elif data['command'] == 'change_username':
                    break

                elif data['command'] == 'change_key':
                    peer_key_dir = os.path.join(main.data_dir, f'{data["peer_id"]}.pub')
                    with open(peer_key_dir, 'w') as file:
                        file.write(data['peer_key'])
                    Logger.info('home_screen: Peer key changed(%s)', data['peer_id'])
        except (ConnectionResetError, ConnectionAbortedError):
            pass

    def add_existing_chat(self, chat: dict) -> None:
        """
        Function to add any existing messages to the chat screen.
        This function is executed in a separate thread.
        """
        # Flag to check if there is an unread message in the chat
        unread = False
        chat_screen = self.chat_screens[chat['chat_id']]

        chat_screen.loading_messages = True
        chat_screen.change_hint_text('Loading messages, it may take a while...', focus=False)

        # Load the chat from the saved chat file
        chat_path = os.path.join(main.data_dir, f'{chat["chat_id"]}.dat')
        if os.path.exists(chat_path):
            with open(chat_path, 'rb') as file:
                saved_chat = pickle.load(file)
        else:
            saved_chat = {}

        # Decrypt the messages that have not been decrypted yet
        # in a separate process and add them to the saved chat
        messages_to_decrypt = [(message[2], main.key_dir) for message in chat['messages']
                               if message[2] not in saved_chat and message[1] == chat['peer_id']]
        if messages_to_decrypt:
            max_processes = int(Config.getint('app', 'max_processes'))
            if not max_processes:
                max_processes = None
            with multiprocessing.Pool(processes=max_processes) as pool:
                decrypted_messages = pool.starmap(main.decrypt_message, messages_to_decrypt)

            saved_chat.update(decrypted_messages)
            with open(chat_path, 'wb') as file:
                pickle.dump(saved_chat, file)
            chat_screen.load_chat()

        # Add the new and existing messages to the chat screen
        for message in chat['messages']:
            chat_screen.add_message(message, animate=False)
            if message[4] and message[1] == chat['peer_id']:
                unread = True

        chat_screen.change_hint_text('Type a message', focus=True)
        chat_screen.loading_messages = False

        # Notify the user of an unread message if there is any
        # new message
        if unread and self.ids.chat_sm.current != chat['chat_id']:
            self.notify(chat['chat_id'])
        else:
            # The user might enter the chat screen before the messages
            # are loaded so mark the chat as read as it would
            # not be done by the on_enter function
            send({'command': 'read_messages', 'chat_id': chat['chat_id']},
                 HomeScreen.current_instance.SERVER)

    @mainthread
    def on_release_peer_chat(self, _id: str) -> None:
        """
        Function to be executed when a peer chat button is released.
        :param _id: The id of the chat
        """

        if not self.ids.chat_sm.current == _id:
            self.ids.chat_sm.current = _id

        else:
            self.ids.chat_sm.current = 'Display'

    @mainthread
    def create_chat(self, chat: dict) -> None:
        """
        Function to create a chat with a peer in the gui.
        It creates a chat button and a chat screen for the chat and
        adds any existing messages to the chat screen.
        :param chat: The chat data received from the server
        """
        # Create a chat button for the chat with the given username
        username = chat['peer_username']
        if username == self.username:
            username += ' (You)'
        chat_button = self.ids.chats.add_peer_button(username, chat['peer_id'])
        chat_button.bind(on_release=lambda *arg: self.on_release_peer_chat(chat['chat_id']))
        if '(You)' in username:
            self.self_chat_button = chat_button

        chat_screen = self.ChatScreen(chat)
        chat_screen.name = chat['chat_id']
        chat_screen.button = chat_button

        if chat['is_user_1']:
            chat_screen.ids.chat_started_label.text = 'You started the chat'
        else:
            chat_screen.ids.chat_started_label.text = f'{chat["peer_username"]} started the chat'

        self.chat_screens[chat['chat_id']] = chat_screen
        self.ids.chat_sm.add_widget(chat_screen)

        Logger.info('home_screen: Chat created(%s)', username)

        # Add any existing messages to the chat screen in a separate
        # thread
        try:
            if chat['messages']:
                ThreadWithExc(target=self.add_existing_chat, args=(chat,)).start()
        except KeyError:
            if chat['is_user_1']:
                self.on_release_peer_chat(chat['chat_id'])

    @mainthread
    def notify(self, chat_id: str) -> None:
        """
        Function to notify the user of an unread message in a chat.
        """
        # Change the color of the chat button to the notification color
        button = self.chat_screens[chat_id].button
        if not button.md_bg_color == NOTIFICATION_COLOR:
            button.md_bg_color = NOTIFICATION_COLOR

    class ChatScreen(MDScreen):
        """Class to handle each chat separately."""

        chat: dict

        # The date of the last message
        date: str | None = None

        # The button that represents the chat in the chats list
        button: MDButton

        message_label = None
        animation: Animation | None = None

        peer_key_dir: str

        saved_chat: dict
        saved_chat_dir: str

        hint_text: StringProperty = StringProperty('Type a message')

        # Whether the chat is currently loading any messages
        loading_messages: bool = False

        def __init__(self, chat: dict, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.chat = chat

            # Save the peer's public key to a file
            self.peer_key_dir = os.path.join(main.data_dir, str(self.chat['peer_id']))
            with open(f'{self.peer_key_dir}.pub', 'w') as file:
                file.write(self.chat['peer_key'])

            self.saved_chat_dir = os.path.join(main.data_dir, f'{self.chat["chat_id"]}.dat')
            self.load_chat()

        def on_enter(self, *args) -> None:
            """Function to be executed when the screen is entered."""
            # Mark the chat as read if it is unread
            if self.button.md_bg_color == NOTIFICATION_COLOR:
                send({'command': 'read_messages', 'chat_id': self.chat['chat_id']},
                     HomeScreen.current_instance.SERVER)
            self.button.md_bg_color = [1, 1, 1, 0.1]
            if not self.loading_messages:
                self.ids.message_input.focus = True

        def on_leave(self, *args) -> None:
            """Function to be executed when the screen is left."""
            self.button.md_bg_color = [1, 1, 1, 0]

        def save_chat(self) -> None:
            """Function to save the chat to a file."""
            with open(self.saved_chat_dir, 'wb') as file:
                pickle.dump(self.saved_chat, file)

        def load_chat(self) -> None:
            """
            Function to load the chat from a file to the saved_chat
            dictionary.
            """
            try:
                with open(self.saved_chat_dir, 'rb') as file:
                    self.saved_chat = pickle.load(file)
            except FileNotFoundError:
                self.saved_chat = {}

        def send_message(self) -> None:
            """Function to send a message to the peer."""

            @raise_exception
            def _send():
                """
                Main function to send the message.
                It is executed in a separate thread.
                """
                message = self.ids.message_input.text.strip()
                if message and not self.loading_messages and len(message) <= 500:
                    # Add the message to the chat screen
                    self.add_message([None, HomeScreen.current_instance._id,  # noqa
                                      message, datetime.now().strftime('%d-%m-%Y %H:%M')],
                                     False)

                    Clock.schedule_once(lambda *args: setattr(self.ids.message_input, 'text', ''))

                    # Encrypt the message in a separate process
                    with multiprocessing.Pool(processes=1) as pool:
                        encrypted_message = pool.starmap(main.encrypt_message,
                                                         [(message, self.peer_key_dir)])
                    if encrypted_message[0] is None:
                        raise Exception('Unable to encrypt message')
                    self.saved_chat.update(encrypted_message)

                    # Send the message to the server
                    data = {
                        'command': 'send_message',
                        'chat_id': self.chat['chat_id'],
                        'peer_id': self.chat['peer_id'],
                        'message': encrypted_message[0][0]

                    }
                    send(data, HomeScreen.current_instance.SERVER)
                    self.save_chat()

            ThreadWithExc(target=_send).start()

        @mainthread
        def add_message(self, message: tuple | list,
                        encrypted: bool = True, animate: bool = True) -> None:
            """
            Function to add a message to the chat screen.
            :param message: The data received from the server
            :param encrypted: Whether the message is encrypted
            :param animate: Whether to animate the message label
            """
            if isinstance(message, tuple):
                message = list(message)

            # Create a message label for the message
            if message[1] == HomeScreen.current_instance._id:  # noqa
                message_label = self.UserMessageLabel()
            else:
                message_label = self.PeerMessageLabel()

            if encrypted:
                message[3] = convert_utc_to_local(message[3])
                try:
                    _message = self.saved_chat[message[2]]
                except KeyError:
                    # None for the message means that the decryption
                    # failed
                    _message = None
            else:
                _message = message[2]
            message_label.add_text(_message)

            date, time = message[3].split()
            # Add a date label if the date of the message is different
            if date != self.date:
                date_label = self.DateLabel()
                date_label.ids.date_label.text = date
                self.ids.chat.add_widget(date_label)
                self.date = date
            message_label.ids.time_label.text = time

            self.ids.chat.add_widget(message_label)
            self.ids.chat_scroll_view.scroll_to(message_label, animate=animate)
            if animate:
                if self.animation and self.message_label:
                    self.animation.stop(self.message_label)
                    self.message_label.opacity = 1
                self.message_label = message_label
                message_label.opacity = 0
                self.animation = Animation(opacity=1, duration=0.4)
                self.animation.start(message_label)

                Clock.schedule_once(lambda *args: setattr(self.ids.message_input, 'focus', True))

            Logger.info('home_screen: Message added(%s) to chat(%s) at %s',
                        _message, self.chat['chat_id'], message[3])

        @mainthread
        def change_hint_text(self, text: StringProperty, focus: bool | None) -> None:
            """
            Function to change the hint text of the message input.
            :param text: The new hint text
            :param focus: Whether to focus the message input and None
                          to keep the current focus
            """
            if focus is None:
                focus = self.ids.message_input.focus
            if self.hint_text != text:
                self.hint_text = text
                self.ids.message_input.focus = not focus
                self.ids.message_input.focus = focus

        class MessageLabel(MDCard):
            """Base class for the message labels."""

            def add_text(self, text: str | None):
                """Function to add text to the message label."""
                if text is None:
                    text = 'Unable to decrypt message'
                    self.ids.message_label.italic = True
                self.ids.message_label.text = text
                for size in SIZES:
                    if size[0] <= len(text) < size[1]:
                        self.width = SIZES[size] * Metrics.dp
                        break
                else:
                    self.width = 400 * Metrics.dp

        class UserMessageLabel(MessageLabel):
            """Class to handle the user message labels."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.pos_hint = {'right': 1}
                self.ids.message_screen.md_bg_color = [1, 0.65, 0, 0.8]

        class PeerMessageLabel(MessageLabel):
            """Class to handle the peer message labels."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.pos_hint = {'left': 1}

        class DateLabel(MDCard):
            """Class to handle the date labels in the chat screen."""

    class PeersList(MDScreen):
        """Class to handle the peer list for the application."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.peers: list[HomeScreen.PeersList.PeerButton] = []

        class PeerButton(MDButton):
            """
            Class to handle the button for peers in the users list.
            """

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._id: str = ''

        def add_peer_button(self, username: str, _id: str) -> PeerButton:
            """
            Function to add a peer button to the list.
            :param username: The username of the user
            :param _id: The id of the peer
            :return: The button added to the list for the peer
            """
            if not self.peers:
                self.ids.peers_list.clear_widgets()

            # Create a peer button for the peer, animate it and add it
            # to the list
            peer_button = self.PeerButton(
                MDButtonText(text=username, theme_text_color='Custom', text_color='white'))
            peer_button._id = _id
            peer_button.opacity = 0

            Animation(opacity=1, duration=0.2).start(peer_button)

            self.ids.peers_list.add_widget(peer_button)
            self.ids.peers_list.add_widget(Widget())
            self.peers.append(peer_button)

            return peer_button

    class SearchPeer(MDScreen):
        """Class to handle the SearchPeer screen."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            Clock.schedule_once(lambda *arg: self.ids.peers_list.ids.peers_list.clear_widgets())

        def on_validate_text_username_input(self) -> None:
            """
            Function executed when the text in the username input is
            validated.
            """
            username = self.ids.username_input.text
            if username:
                # Send the search peer command to the server
                server = HomeScreen.current_instance.SERVER
                data = {
                    'command': 'search_peer',
                    'username': username
                }
                send(data, server)

        @mainthread
        def add_peers(self, peers: list | None) -> None:
            """Function to the search results to the peers list."""
            if peers:
                self.ids.peers_list.ids.peers_list.clear_widgets()
                for peer in peers:
                    peer_button = self.ids.peers_list.add_peer_button(peer[3], peer[0])
                    peer_button.bind(on_release=self.on_release_peer_button)
            else:
                self.ids.username_input.error = True

        @staticmethod
        def on_release_peer_button(*args) -> None:
            """
            Function to be executed when a peer button is released.
            """
            _id = args[0]._id  # noqa
            # Create a chat with the peer if a chat with the peer does
            # not already exist otherwise set the current chat screen
            # to the chat with the peer
            if _id not in [HomeScreen.current_instance.chat_screens[chat].chat['peer_id']
                           for chat in HomeScreen.current_instance.chat_screens]:
                server = HomeScreen.current_instance.SERVER
                data = {
                    'command': 'create_chat',
                    'peer_id': _id
                }
                send(data, server)
                HomeScreen.current_instance.on_release_search_peer()
            else:
                chat_screens = HomeScreen.current_instance.chat_screens
                for chat in chat_screens:
                    if chat_screens[chat].chat['peer_id'] == _id:
                        HomeScreen.current_instance.ids.chat_sm.current = chat
                        break
