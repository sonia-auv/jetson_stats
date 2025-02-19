# -*- coding: UTF-8 -*-
# This file is part of the jetson_stats package (https://github.com/rbonghi/jetson_stats or http://rnext.it).
# Copyright (c) 2019 Raffaello Bonghi.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import abc
import curses
import signal
# Logging
import logging
# Graphics elements
from .jtopguilib import (check_size,
                         check_curses,
                         set_xterm_title,
                         xterm_line)
# Create logger for jplotlib
logger = logging.getLogger(__name__)
# Initialization abstract class
# In according with: https://gist.github.com/alanjcastonguay/25e4db0edd3534ab732d6ff615ca9fc1
ABC = abc.ABCMeta('ABC', (object,), {})


class Page(ABC):

    def __init__(self, name, stdscr, jetson, refresh):
        self.name = name
        self.stdscr = stdscr
        self.jetson = jetson
        self.refresh = refresh

    def size_page(self):
        height, width = self.stdscr.getmaxyx()
        first = 0
        # Remove a line for sudo header
        if self.jetson.userid != 0:
            height -= 1
            first = 1
        return height, width, first

    @abc.abstractmethod
    @check_curses
    def draw(self, key):
        pass

    def keyboard(self, key):
        pass


class JTOPGUI:
    """
        The easiest way to use curses is to use a wrapper around a main function
        Essentially, what goes in the main function is the body of your program,
        The `stdscr' parameter passed to it is the curses screen generated by our
        wrapper.
    """
    COLORS = {"RED": 1, "GREEN": 2, "YELLOW": 3, "BLUE": 4, "MAGENTA": 5, "CYAN": 6}

    def __init__(self, stdscr, refresh, jetson, pages, init_page=0, start=True):
        # Define pairing colors
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_RED)
        # Set curses reference, refresh and jetson controller
        self.stdscr = stdscr
        self.refresh = refresh
        self.jetson = jetson
        # Initialize all Object pages
        self.pages = [obj(stdscr, jetson, refresh) for obj in pages]
        # Set default page
        self.n_page = 0
        self.set(init_page)
        # Initialize keyboard status
        self.key = -1
        self.old_key = -1
        self.signal = True
        # Catch all signals
        for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
            signal.signal(sig, self.handler)
        # Run the GUI
        if start:
            self.run()

    def handler(self, signum=None, frame=None):
        logger.info("Signal handler called with signal {signum}".format(signum=signum))
        # Close gui
        self.signal = False

    def run(self):
        # In this program, we don't want keystrokes echoed to the console,
        # so we run this to disable that
        curses.noecho()
        # Additionally, we want to make it so that the user does not have to press
        # enter to send keys to our program, so here is how we get keys instantly
        curses.cbreak()
        # Try to hide the cursor
        if hasattr(curses, 'curs_set'):
            try:
                curses.curs_set(0)
            except Exception:
                pass
        # Lastly, keys such as the arrow keys are sent as funny escape sequences to
        # our program. We can make curses give us nicer values (such as curses.KEY_LEFT)
        # so it is easier on us.
        self.stdscr.keypad(True)
        # Refreshing page curses loop
        # https://stackoverflow.com/questions/54409978/python-curses-refreshing-text-with-a-loop
        self.stdscr.nodelay(1)
        """ Here is the loop of our program, we keep clearing and redrawing in this loop """
        while self.keyboard() and self.signal:
            # Draw pages
            self.draw()

    @check_size(20, 50)
    def draw(self):
        # First, clear the screen
        self.stdscr.erase()
        # Write head of the jtop
        self.header()
        # Get page selected
        page = self.pages[self.n_page]
        # Draw the page
        page.draw(self.key)
        # Draw menu
        self.menu()
        # Draw the screen
        self.stdscr.refresh()
        # Set a timeout and read keystroke
        self.stdscr.timeout(self.refresh)

    def increase(self):
        idx = self.n_page + 1
        self.set(idx + 1)

    def decrease(self):
        idx = self.n_page + 1
        self.set(idx - 1)

    def set(self, idx):
        if idx <= len(self.pages) and idx > 0:
            self.n_page = idx - 1

    @check_curses
    def header(self):
        # Title script
        # Reference: https://stackoverflow.com/questions/25872409/set-gnome-terminal-window-title-in-python
        # Print jtop basic info
        set_xterm_title("jtop" + xterm_line(self.jetson))
        # Write first line
        board = self.jetson.board["info"]
        # Add extra Line if without sudo
        idx = 0
        if self.jetson.userid != 0:
            _, width = self.stdscr.getmaxyx()
            self.stdscr.addstr(0, 0, ("{0:<" + str(width) + "}").format(" "), curses.color_pair(7))
            string_sudo = "SUDO REQUIRED"
            self.stdscr.addstr(0, (width - len(string_sudo)) // 2, string_sudo, curses.color_pair(7))
            idx = 1
        self.stdscr.addstr(idx, 0, board["Machine"] + " - Jetpack " + board["Jetpack"], curses.A_BOLD)

    @check_curses
    def menu(self):
        height, width = self.stdscr.getmaxyx()
        # Set background for all menu line
        self.stdscr.addstr(height - 1, 0, ("{0:<" + str(width - 1) + "}").format(" "), curses.A_REVERSE)
        position = 1
        for idx, page in enumerate(self.pages):
            if self.n_page != idx:
                self.stdscr.addstr(height - 1, position, ("{idx} {name}").format(idx=idx + 1, name=page.name), curses.A_REVERSE)
            else:
                self.stdscr.addstr(height - 1, position, ("{idx} {name}").format(idx=idx + 1, name=page.name))
            position += len(page.name) + 2
            if idx < len(self.pages) - 1:
                self.stdscr.addstr(height - 1, position, " - ", curses.A_REVERSE)
                position += 3
        # Author name
        name_author = "Raffaello Bonghi"
        self.stdscr.addstr(height - 1, width - len(name_author), name_author, curses.A_REVERSE)

    def keyboard(self):
        self.key = self.stdscr.getch()
        if self.old_key != self.key:
            # keyboard check list
            if self.key == curses.KEY_LEFT:
                self.decrease()
            elif self.key == curses.KEY_RIGHT:
                self.increase()
            elif self.key in [ord(str(n)) for n in range(10)]:
                num = int(chr(self.key))
                self.set(num)
            elif self.key == ord('q') or self.key == ord('Q') or self.ESC_BUTTON(self.key):
                # keyboard check quit button
                return False
            else:
                page = self.pages[self.n_page]
                # Run key controller
                page.keyboard(self.key)
            # Store old value key
            self.old_key = self.key
        return True

    def ESC_BUTTON(self, key):
        """
            Check there is another character prevent combination ALT + <OTHER CHR>
            https://stackoverflow.com/questions/5977395/ncurses-and-esc-alt-keys
        """
        if key == 27:
            n = self.stdscr.getch()
            if n == -1:
                return True
        return False
# EOF
