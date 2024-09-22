# -*- coding: utf-8 -*-
"""
PeerChat is a simple messaging application that uses quantum-safe
end-to-end encryption to secure messages.
This is the main execution script for the client side of the
application. It is responsible for handling the window creation,
initializing the connection to the server, managing the screens, etc.
"""

__author__ = 'Oldmacintosh'
__version__ = 'v1.1.1'
__date__ = 'September 2024'
__PROJECT__ = 'PeerChat'
__DEBUG__ = False

# These constants are used as the default values for the config.ini
HOST: str = '45.79.122.54'
PORT: int = 8080
# Max processes to run in parallel for decryption for each chat
MAX_PROCESSES: int = 2

import os  # noqa PEP 8: E402
import uuid  # noqa PEP 8: E402
import pickle  # noqa PEP 8: E402
import logging  # noqa PEP 8: E402
import pq_ntru  # noqa PEP 8: E402

# Define all the necessary directories
main_dir: str = os.path.join(os.path.expanduser(r'~\AppData\Local'), __PROJECT__)
logging_dir: str = os.path.join(main_dir, 'logs')
data_dir: str = os.path.join(main_dir, 'data')
key_dir: str = os.path.join(data_dir, str(uuid.getnode()))


def get_mac_address() -> str:
    """Function to get the MAC address of the system."""
    mac = uuid.getnode()
    mac_address = (':'.join(['{:02x}'.format((mac >> elements) & 0xff)
                             for elements in range(0, 2 * 6, 2)][::-1]))
    return mac_address


# The functions are used by the home_screen module to encrypt and
# decrypt messages in a separate process to avoid freezing or lagging
# the main thread.

def encrypt_message(message: str, peer_key_dir: str) -> tuple[str, str] | None:
    """
    Function to encrypt the message using the public key of the
    peer.
    :param message: The message to encrypt
    :param peer_key_dir: The directory of the public key of the peer
    :return: The encrypted message and the original message, it
             returns None if the encryption fails.
    """
    try:
        return pq_ntru.encrypt(peer_key_dir, message), message
    except Exception as _error:
        logging.exception('main: Error while encrypting message(%s)', _error)
        return None


def decrypt_message(message: str, _key_dir: str) -> tuple[str, str | None]:
    """
    Function to decrypt the message using the private key of the
    user.
    :param message: The message to decrypt
    :param _key_dir: The directory of the private key of the user
    :return: The original message and the decrypted message, the
             decrypted message is None if the decryption fails.
    Note: A separate argument for the key directory is used to
    avoid conflicts with the key_dir variable in the main script
    that might be changed during testing or debugging.
    """
    try:
        decrypted_message = pq_ntru.decrypt(_key_dir, message)
    except ValueError:
        decrypted_message = None
    except Exception as _error:
        logging.exception('main: Error while decrypting message(%s)', _error)
        decrypted_message = None
    return message, decrypted_message


if __name__ == '__main__':
    import time
    import sys
    import socket
    import multiprocessing
    from tblib import pickling_support
    import pymsgbox

    try:
        multiprocessing.freeze_support()
        if not __DEBUG__:
            os.environ['KIVY_NO_CONSOLELOG'] = '1'
            try:
                # Ensure that only one instance of the application is
                # running if not in debug mode
                for file in os.listdir(logging_dir) if os.path.exists(logging_dir) else []:
                    if not file.endswith('.txt'):
                        continue
                    file = os.path.join(logging_dir, file)
                    os.rename(file, file)
            except PermissionError as error:
                raise RuntimeError('Another instance of PeerChat is already running.') from error
        from dependencies.modules.thread_with_exc import ThreadWithExc
        from dependencies.modules.communicator import send, receive
        from dependencies.modules import kivy_config
        from dependencies.modules.raise_exc import raise_exception
        from dependencies.modules.home_screen import HomeScreen
        from kivy.metrics import Metrics
        from kivy.core.window import Window
        from kivy.lang import Builder
        from kivy.config import Config
        from kivy.logger import Logger
        from kivy.properties import StringProperty
        from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
        from kivy.clock import Clock, ClockEvent, mainthread
        from kivy.uix.label import Label
        from kivymd.app import MDApp
        from kivymd.uix.screen import MDScreen

        pickling_support.install()

        ADDR: tuple[str, int] | None = None
        SERVER: socket.socket | None = None


        def keep_alive(_socket: socket.socket) -> None:
            """
            Function to keep the connection alive by sending a
            keep-alive signal to the server.
            :param _socket: The socket object to keep alive.
            """
            _socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            _socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)


        class EmptyScreen(Screen):
            """
            An empty screen to be used as a placeholder, transitions to
            the splash screen on startup. Using this screen helps to
            load all the widgets without any lag. It also updates the
            screen size in the config.ini  file when the window is
            closed.
            """

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                Window.bind(on_resize=self.on_resize)

            def on_enter(self, *args) -> None:
                """Executed when the screen is entered."""
                Clock.schedule_once(lambda *arg: setattr(self.parent, 'current', 'Splash'))

            @staticmethod
            def on_resize(*args) -> None:
                """Executed when the window is resized."""
                # Save the size of the window to the config file
                Config.set('graphics', 'height', int(args[2] / Metrics.dp))
                Config.set('graphics', 'width', int(args[1] / Metrics.dp))
                Config.write()


        class SplashScreen(MDScreen):
            """
            The Application loads in to this screen first to
            connect to the server while playing the animation and
            transition to the necessary screen.
            """

            def on_enter(self, *args) -> None:
                """Executed when the screen is entered."""
                # Play the animation and start loading the app
                Clock.schedule_once(lambda *arg: self.ids.name_typer.typewrite(
                    string='PeerChat', time_period=0.1, on_complete=self.load_thread), 0.5)

            def on_leave(self, *args) -> None:
                """Executed when the screen is left."""
                # Reset the screen widgets to the initial state if the
                # splash screen is needed again
                self.ids.loader.color = [1, 1, 1, 0]
                self.ids.name_typer.text = ''
                self.ids.status_label.text = ''

            def load_thread(self) -> None:
                """
                Function to start loading in a thread to avoid freezing
                of the app.
                """
                Logger.info('main: The app is loading')
                self.parent.transition = SlideTransition(direction='up')
                self.ids.loader.color = [1, 1, 1, 1]
                Clock.schedule_once(lambda *arg: ThreadWithExc(target=self.start_loading).start())

            @raise_exception
            def start_loading(self) -> None:
                """
                Starts the actual loading of the app.
                It connects adds the home screen to the screen manager,
                connects to the server, generates the keys, and syncs
                the chats.
                """
                try:
                    global ADDR, SERVER

                    # Flag to check if the home screen has been added
                    # as it can only be added in the main thread.
                    home_screen_added: bool = False

                    @mainthread
                    def add_home_screen() -> None:
                        """
                        Function to add the home screen to the
                        screen manager.
                        """
                        nonlocal home_screen_added
                        if HomeScreen.current_instance:
                            Logger.info('main: Removing the current home screen')
                            self.parent.remove_widget(HomeScreen.current_instance)
                        home_screen = HomeScreen()
                        self.parent.add_widget(home_screen)
                        self.parent.ids['Home'] = home_screen
                        home_screen_added = True
                        Logger.info('main: Home screen added successfully')

                    add_home_screen()

                    # Create the public and private keys for the user
                    if any([not os.path.exists(fr'{key_dir}.pub'),
                            not os.path.exists(fr'{key_dir}.priv')]):
                        self.change_status('Generating a new key pair')
                        process = multiprocessing.Process(target=pq_ntru.generate_keys,
                                                          args=(key_dir, 'moderate', True))
                        process.start()
                        process.join()
                        Logger.info('main: Keys generated')

                    self.change_status('Connecting to the server')
                    ADDR = (Config.get('server', 'host'), Config.getint('server', 'port'))
                    SERVER = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    SERVER.connect(ADDR)
                    keep_alive(SERVER)
                    # Send the project name and version to the server
                    SERVER.send(bytes(f'{__PROJECT__}_{__version__}', 'utf-8'))
                    message = receive(SERVER)
                    if message != 'Connected':
                        raise ConnectionResetError
                    Logger.info('main: Connected to the server')

                    if not __DEBUG__:
                        send(get_mac_address(), SERVER)
                    else:
                        send(__PROJECT__, SERVER)

                    with open(f'{key_dir}.pub') as _file:
                        public_key = _file.read()
                    send(public_key, SERVER)

                    while not home_screen_added:
                        pass
                    self.parent.ids.Home.SERVER = SERVER
                    self.parent.ids.Home.ADDR = ADDR

                    message = receive(SERVER)
                    if message == 'unregistered':
                        Logger.info('main: User is not registered')
                        self.change_screen('UserName')
                    else:
                        data = receive(SERVER)
                        self.parent.ids.Home._id = data[0]
                        self.parent.ids.Home.username = data[1]

                        self.change_status('Syncing chats')
                        while True:
                            data = receive(SERVER)
                            if data == 'sync complete':
                                break
                            self.parent.ids.Home.create_chat(data)

                        Logger.info('main: Chats synced successfully')
                        self.change_screen('Home')

                except (ConnectionRefusedError, ConnectionResetError):
                    self.change_status('Unable to connect to the server')
                    self.change_screen('ServerAdd')

            def change_screen(self, screen: str) -> None:
                """
                Changes the screen of the screen manager to the
                specified screen.
                :param screen: The screen to change to.
                """

                @mainthread
                def update_gui() -> None:
                    """Updates the screen of the screen manager."""
                    self.parent.current = screen

                update_gui()
                if not __DEBUG__:
                    time.sleep(1)

            def change_status(self, status: str) -> None:
                """Changes the text of the status label."""

                @mainthread
                def update_gui() -> None:
                    """Updates the status label."""
                    self.ids.status_label.text = status

                update_gui()
                if not __DEBUG__:
                    time.sleep(0.5)


        class ServerAddScreen(MDScreen):
            """
            This screen is used to input the server address from the
            user.
            """

            def on_pre_enter(self, *args) -> None:
                """Executed before the screen is entered."""
                self.ids.server_input.text = \
                    f'{Config.get("server", "host")}:{Config.get("server", "port")}'

            def on_text_validate_server_input(self) -> None:
                """
                Function executed on validation of text in the server
                input.
                """
                server_input = self.ids.server_input.text
                if server_input:
                    try:
                        # Check if the server input is valid
                        host, port = server_input.split(':')
                        int(port)
                        # Save the server input to the config file
                        # and change the screen to the splash screen
                        Config.set('server', 'host', host)
                        Config.set('server', 'port', port)
                        Config.write()
                        Clock.schedule_once(lambda *arg: setattr(self.parent, 'current', 'Splash'))
                        Logger.info('main: Server address saved(%s)', server_input)
                    except ValueError:
                        self.ids.server_input.error = True


        class UserNameScreen(MDScreen):
            """
            This screen is used to input the username from the user and
            validate it with the server before proceeding to the
            home screen.
            """

            hint_text = StringProperty('Enter your username')

            def on_text_validate_username_input(self) -> None:
                """
                Function executed on validation of text in the username
                input.
                """
                username = self.ids.username_input.text
                # Check if the username is valid
                if username and len(username) <= 20:
                    username = username.strip()
                    # Send the username to the server for validation
                    send(username, SERVER)
                    message = receive(SERVER)
                    if message == 'username accepted':
                        Logger.info('main: Reinitializing the app with the username(%s)', username)
                        SERVER.close()
                        self.parent.transition = SlideTransition(direction='up')
                        self.parent.current = 'Splash'
                        self.ids.username_input.text = ''
                    else:
                        self.ids.username_input.error = True
                        message = message.capitalize()
                        self.change_hint_text(message)
                        Logger.info('main: %s(%s)', message, username)

            def change_hint_text(self, text: str) -> None:
                """Changes the hint text of the username input."""
                if self.hint_text != text:
                    self.ids.username_input.focus = False
                    self.ids.username_input.focus = True


        class TypeWriter(Label):
            """A label that types the text in it."""

            def typewrite(self, string, time_period, on_complete: callable = None) -> None:
                """
                Function to execute the typewriter effect in the label.
                :param string: The string to type.
                :param time_period: Time between each character.
                :param on_complete: Function to execute on completion.
                """

                typewriter = Clock.create_trigger(lambda *arg: typeit(), time_period)
                typewriter()

                def typeit() -> None:
                    """Adds the text to the label."""
                    nonlocal string
                    self.text += string[0]
                    string = string[1:]
                    if len(string) > 0:
                        typewriter()
                    else:
                        if on_complete:
                            Clock.schedule_once(lambda *arg: on_complete(), 1)


        class PeerChat(MDApp):
            """The main application class for PeerChat."""

            screen_manager: ScreenManager = None

            class SM(ScreenManager):
                """The screen manager for PeerChat."""

            def build(self) -> ScreenManager:
                self.theme_cls.theme_style = 'Dark'

                for kv_file in os.listdir(r'dependencies/kv'):
                    Builder.load_file(os.path.join(r'dependencies/kv', kv_file))

                self.screen_manager = self.SM()
                return self.screen_manager


        app_instance = PeerChat()
        app_instance.run()

    except KeyboardInterrupt:
        pass
    except Exception as error:
        from kivy.logger import Logger

        pickle.dumps(sys.exc_info())
        Logger.exception('main: %s', error)
        if not __DEBUG__:
            pymsgbox.alert(text=f'Exception: "{error}"', title='PeerChat', button='OK')
    # Close the server and the window just in case
    if Window:
        Window.close()
    if HomeScreen.current_instance:
        server = HomeScreen.current_instance.SERVER
        if server:
            server.close()
