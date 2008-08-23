"""
Copyright 2008 Free Software Foundation, Inc.
This file is part of GNU Radio

GNU Radio Companion is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

GNU Radio Companion is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
"""
##@package grc.gui.MainWindow
#The main window, containing all windows, tool bars, and menu bars.
#@author Josh Blum

from grc.Constants import *
from grc.Actions import *
import pygtk
pygtk.require('2.0')
import gtk
import Bars
from BlockTreeWindow import BlockTreeWindow
from Dialogs import TextDisplay,MessageDialogHelper
from DrawingArea import DrawingArea
from grc import Preferences
from grc import Messages
from NotebookPage import Page
import os

############################################################
# Main window
############################################################

class MainWindow(gtk.Window):
	"""The topmost window with menus, the tool bar, and other major windows."""

	def __init__(self, handle_states, platform):
		"""!
		MainWindow contructor.
		@param handle_states the callback function
		"""
		self._platform = platform
		#setup window
		self.handle_states = handle_states
		gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
		vbox = gtk.VBox()
		hbox = gtk.HBox()
		self.add(vbox)
		#create the menu bar and toolbar
		vbox.pack_start(Bars.MenuBar(), False)
		vbox.pack_start(Bars.Toolbar(), False)
		#setup scrolled window
		self.scrolled_window = gtk.ScrolledWindow()
		self.scrolled_window.set_size_request(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
		self.scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.drawing_area = DrawingArea(self)
		self.scrolled_window.add_with_viewport(self.drawing_area)
		#create the notebook
		self.notebook = gtk.Notebook()
		self.page_to_be_closed = None
		self.current_page = None
		self.notebook.set_show_border(False)
		self.notebook.set_scrollable(True) #scroll arrows for page tabs
		self.notebook.connect('switch-page', self._handle_page_change)
		fg_and_report_box = gtk.VBox(False, 0)
		fg_and_report_box.pack_start(self.notebook, False, False, 0)
		fg_and_report_box.pack_start(self.scrolled_window)
		hbox.pack_start(fg_and_report_box)
		vbox.pack_start(hbox)
		#create the side windows
		side_box = gtk.VBox()
		hbox.pack_start(side_box, False)
		side_box.pack_start(BlockTreeWindow(platform, self.get_flow_graph)) #allow resize, selection window can have more space
		#create the reports window
		self.text_display = TextDisplay()
		#house the reports in a scrolled window
		self.reports_scrolled_window = gtk.ScrolledWindow()
		self.reports_scrolled_window.set_size_request(-1, REPORTS_WINDOW_HEIGHT)
		self.reports_scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.reports_scrolled_window.add_with_viewport(self.text_display)
		fg_and_report_box.pack_end(self.reports_scrolled_window, False) #dont allow resize, fg should get all the space
		#show all but the main window container and the reports window
		vbox.show_all()
		self.notebook.hide()
		self._show_reports_window(False)
		# load preferences and show the main window
		Preferences.load(platform)
		self.resize(*Preferences.window_size())
		self.show()#show after resize in preferences

	############################################################
	# Event Handlers
	############################################################

	def _quit(self, window, event):
		"""!
		Handle the delete event from the main window.
		Generated by pressing X to close, alt+f4, or right click+close.
		This method in turns calls the state handler to quit.
		@return true
		"""
		self.handle_states(APPLICATION_QUIT)
		return True

	def _handle_page_change(self, notebook, page, page_num):
		"""!
		Handle a page change. When the user clicks on a new tab,
		reload the flow graph to update the vars window and
		call handle states (select nothing) to update the buttons.
		@param notebook the notebook
		@param page new page
		@param page_num new page number
		"""
		self.current_page = self.notebook.get_nth_page(page_num)
		Messages.send_page_switch(self.current_page.get_file_path())
		self.handle_states()

	############################################################
	# Report Window
	############################################################

	def add_report_line(self, line):
		"""!
		Place line at the end of the text buffer, then scroll its window all the way down.
		@param line the new text
		"""
		self.text_display.insert(line)
		vadj = self.reports_scrolled_window.get_vadjustment()
		vadj.set_value(vadj.upper)
		vadj.emit('changed')

	def _show_reports_window(self, show):
		"""!
		Show the reports window when show is True.
		Hide the reports window when show is False.
		@param show boolean flag
		"""
		if show: self.reports_scrolled_window.show()
		else: self.reports_scrolled_window.hide()

	############################################################
	# Pages: create and close
	############################################################

	def new_page(self, file_path='', show=False):
		"""!
		Create a new notebook page.
		Set the tab to be selected.
		@param file_path optional file to load into the flow graph
		@param show true if the page should be shown after loading
		"""
		#if the file is already open, show the open page and return
		if file_path and file_path in self._get_files(): #already open
			page = self.notebook.get_nth_page(self._get_files().index(file_path))
			self._set_page(page)
			return
		try: #try to load from file
			if file_path: Messages.send_start_load(file_path)
			flow_graph = self._platform.get_new_flow_graph()
			#inject drawing area and handle states into flow graph
			flow_graph.drawing_area = self.drawing_area
			flow_graph.handle_states = self.handle_states
			page = Page(
				self,
				flow_graph=flow_graph,
				file_path=file_path,
			)
			if file_path: Messages.send_end_load()
		except Exception, e: #return on failure
			Messages.send_fail_load(e)
			return
		#add this page to the notebook
		self.notebook.append_page(page, page.get_tab())
		try: self.notebook.set_tab_reorderable(page, True)
		except: pass #gtk too old
		self.notebook.set_tab_label_packing(page, False, False, gtk.PACK_START)
		#only show if blank or manual
		if not file_path or show: self._set_page(page)

	def close_pages(self):
		"""
		Close all the pages in this notebook.
		@return true if all closed
		"""
		open_files = filter(lambda file: file, self._get_files()) #filter blank files
		open_file = self.get_page().get_file_path()
		#close each page
		for page in self._get_pages():
			self.page_to_be_closed = page
			self.close_page(False)
		if self.notebook.get_n_pages(): return False
		#save state before closing
		Preferences.files_open(open_files)
		Preferences.file_open(open_file)
		Preferences.window_size(self.get_size())
		Preferences.save()
		return True

	def close_page(self, ensure=True):
		"""
		Close the current page.
		If the notebook becomes empty, and ensure is true,
		call new page upon exit to ensure that at least one page exists.
		@param ensure boolean
		"""
		if not self.page_to_be_closed: self.page_to_be_closed = self.get_page()
		#show the page if it has an executing flow graph or is unsaved
		if self.page_to_be_closed.get_pid() or not self.page_to_be_closed.get_saved():
			self._set_page(self.page_to_be_closed)
		#unsaved? ask the user
		if not self.page_to_be_closed.get_saved() and self._save_changes():
			self.handle_states(FLOW_GRAPH_SAVE) #try to save
			if not self.page_to_be_closed.get_saved(): #still unsaved?
				self.page_to_be_closed = None #set the page to be closed back to None
				return
		#stop the flow graph if executing
		if self.page_to_be_closed.get_pid(): self.handle_states(FLOW_GRAPH_KILL)
		#remove the page
		self.notebook.remove_page(self.notebook.page_num(self.page_to_be_closed))
		if ensure and self.notebook.get_n_pages() == 0: self.new_page() #no pages, make a new one
		self.page_to_be_closed = None #set the page to be closed back to None

	############################################################
	# Misc
	############################################################

	def update(self):
		"""!
		Set the title of the main window.
		Set the titles on the page tabs.
		Show/hide the reports window.
		@param title the window title
		"""
		if self.get_page():
			title = ''.join((
					MAIN_WINDOW_PREFIX,
					' - Editing: ',
					(self.get_page().get_file_path() or NEW_FLOGRAPH_TITLE),
					(self.get_page().get_saved() and ' ' or '*'), #blank must be non empty
				)
			)
		else: title = MAIN_WINDOW_PREFIX + ' - Editor '
		gtk.Window.set_title(self, title)
		#set tab titles
		for page in self._get_pages():
			title = os.path.basename(page.get_file_path())
			#strip file extension #TEMP
			if title.endswith('.xml'): 
				title = title[0:-len('.xml')]
			#strip file extension
			if title.endswith(FLOW_GRAPH_FILE_EXTENSION): 
				title = title[0:-len(FLOW_GRAPH_FILE_EXTENSION)]
			page.set_text(''.join((
						(title or NEW_FLOGRAPH_TITLE),
						(page.get_saved() and ' ' or '*'), #blank must be non empty
					)
				)
			)
		#reports window
		self._show_reports_window(Preferences.show_reports_window())
		#show/hide notebook tabs
		if len(self._get_pages()) > 1: self.notebook.show()
		else: self.notebook.hide()

	def get_page(self):
		"""!
		Get the selected page.
		@return the selected page
		"""
		return self.current_page

	def get_flow_graph(self):
		"""!
		Get the selected flow graph.
		@return the selected flow graph
		"""
		return self.get_page().get_flow_graph()

	############################################################
	# Helpers
	############################################################

	def _set_page(self, page):
		"""!
		Set the current page.
		@param page the page widget
		"""
		self.current_page = page
		self.notebook.set_current_page(self.notebook.page_num(self.current_page))

	def _save_changes(self):
		"""!
		Save changes to flow graph?
		@return true if yes
		"""
		return MessageDialogHelper(
			gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 'Unsaved Changes!',
			'Would you like to save changes before closing?'
		) == gtk.RESPONSE_YES

	def _get_files(self):
		"""
		Get the file names for all the pages, in order.
		@return list of file paths
		"""
		return map(lambda page: page.get_file_path(), self._get_pages())

	def _get_pages(self):
		"""
		Get a list of all pages in the notebook.
		@return list of pages
		"""
		return [self.notebook.get_nth_page(page_num) for page_num in range(self.notebook.get_n_pages())]

