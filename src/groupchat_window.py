##	plugins/groupchat_window.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##
##	Copyright (C) 2003-2005 Gajim Team
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import gtk
import gtk.glade
import pango
import gobject
import time
import dialogs
import chat
import cell_renderer_image
from common import gajim
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE='gtkgui.glade'

class Groupchat_window(chat.Chat):
	"""Class for Groupchat window"""
	def __init__(self, room_jid, nick, plugin, account):
		chat.Chat.__init__(self, plugin, account, 'groupchat_window')
		self.nicks = {}
		self.list_treeview = {}
		self.subjects = {}
		self.new_group(room_jid, nick)
		self.show_title()
		self.xml.signal_connect('on_groupchat_window_destroy', \
			self.on_groupchat_window_destroy)
		self.xml.signal_connect('on_groupchat_window_delete_event', \
			self.on_groupchat_window_delete_event)
		self.xml.signal_connect('on_groupchat_window_focus_in_event', \
			self.on_groupchat_window_focus_in_event)
		self.xml.signal_connect('on_chat_notebook_key_press_event', \
			self.on_chat_notebook_key_press_event)
		self.xml.signal_connect('on_chat_notebook_switch_page', \
			self.on_chat_notebook_switch_page)
		self.xml.signal_connect('on_set_button_clicked', \
			self.on_set_button_clicked)
		self.xml.signal_connect('on_groupchat_window_key_press_event', \
			self.on_groupchat_window_key_press_event)

	def on_groupchat_window_delete_event(self, widget, event):
		"""close window"""
		for room_jid in self.xmls:
			if time.time() - self.last_message_time[room_jid] < 2:
				dialog = dialogs.Confirmation_dialog(_('You received a message in the room %s in the last two seconds.\nDo you still want to close this window?') % \
					room_jid.split('@')[0])
				if dialog.get_response() != gtk.RESPONSE_YES:
					return True #stop the propagation of the event
	
	def on_groupchat_window_destroy(self, widget):
		for room_jid in self.xmls:
			gajim.connections[self.account].send_gc_status(self.nicks[room_jid], \
				room_jid, 'offline', 'offline')
		chat.Chat.on_window_destroy(self, widget, 'gc')

	def on_groupchat_window_focus_in_event(self, widget, event):
		"""When window get focus"""
		chat.Chat.on_chat_window_focus_in_event(self, widget, event)

	def on_chat_notebook_key_press_event(self, widget, event):
		chat.Chat.on_chat_notebook_key_press_event(self, widget, event)
	
	def on_chat_notebook_switch_page(self, notebook, page, page_num):
		new_child = notebook.get_nth_page(page_num)
		new_jid = ''
		for jid in self.xmls:
			if self.childs[jid] == new_child: 
				new_jid = jid
				break
		self.xml.get_widget('subject_entry').set_text(\
			self.subjects[new_jid])
		chat.Chat.on_chat_notebook_switch_page(self, notebook, page, page_num)

	def get_role_iter(self, room_jid, role):
		model = self.list_treeview[room_jid].get_model()
		fin = False
		iter = model.get_iter_root()
		if not iter:
			return None
		while not fin:
			role_name = model.get_value(iter, 2)
			if role == role_name:
				return iter
			iter = model.iter_next(iter)
			if not iter:
				fin = True
		return None

	def get_user_iter(self, room_jid, nick):
		model = self.list_treeview[room_jid].get_model()
		fin = False
		role_iter = model.get_iter_root()
		if not role_iter:
			return None
		while not fin:
			fin2 = False
			user_iter = model.iter_children(role_iter)
			if not user_iter:
				fin2=True
			while not fin2:
				if nick == model.get_value(user_iter, 1):
					return user_iter
				user_iter = model.iter_next(user_iter)
				if not user_iter:
					fin2 = True
			role_iter = model.iter_next(role_iter)
			if not role_iter:
				fin = True
		return None

	def get_nick_list(self, room_jid):
		model = self.list_treeview[room_jid].get_model()
		list = []
		fin = False
		role = model.get_iter_root()
		if not role:
			return list
		while not fin:
			fin2 = False
			user = model.iter_children(role)
			if not user:
				fin2=True
			while not fin2:
				nick = model.get_value(user, 1)
				list.append(nick)
				user = model.iter_next(user)
				if not user:
					fin2 = True
			role = model.iter_next(role)
			if not role:
				fin = True
		return list

	def remove_user(self, room_jid, nick):
		"""Remove a user from the roster"""
		model = self.list_treeview[room_jid].get_model()
		iter = self.get_user_iter(room_jid, nick)
		if not iter:
			return
		parent_iter = model.iter_parent(iter)
		model.remove(iter)
		if model.iter_n_children(parent_iter) == 0:
			model.remove(parent_iter)
	
	def add_user_to_roster(self, room_jid, nick, show, role, jid):
		model = self.list_treeview[room_jid].get_model()
		img = self.plugin.roster.pixbufs[show]
		role_iter = self.get_role_iter(room_jid, role)
		if not role_iter:
			role_iter = model.append(None, (self.plugin.roster.pixbufs['closed']\
				, role + 's', role, ''))
		iter = model.append(role_iter, (img, nick, jid, show))
		self.list_treeview[room_jid].expand_row((model.get_path(role_iter)), \
			False)
		return iter
	
	def get_role(self, room_jid, jid_iter):
		model = self.list_treeview[room_jid].get_model()
		path = model.get_path(jid_iter)[0]
		iter = model.get_iter(path)
		return model.get_value(iter, 2)

	def udpate_pixbufs(self):
		for room_jid in self.list_treeview:
			model = self.list_treeview[room_jid].get_model()
			role_iter = model.get_iter_root()
			if not role_iter:
				continue
			while role_iter:
				user_iter = model.iter_children(role_iter)
				if not user_iter:
					continue
				while user_iter:
					show = model.get_value(user_iter, 3)
					img = self.plugin.roster.pixbufs[show]
					model.set_value(user_iter, 0, img)
					user_iter = model.iter_next(user_iter)
				role_iter = model.iter_next(role_iter)

	def chg_user_status(self, room_jid, nick, show, status, role, affiliation, \
		jid, reason, actor, statusCode, account):
		"""When a user change his status"""
		model = self.list_treeview[room_jid].get_model()
		if show == 'offline' or show == 'error':
			if statusCode == '307':
				self.print_conversation(_('%s has been kicked by %s: %s') % (nick, \
					jid, actor, reason))
			self.remove_user(room_jid, nick)
		else:
			iter = self.get_user_iter(room_jid, nick)
			ji = jid
			if jid:
				ji = jid.split('/')[0]
			if not iter:
				iter = self.add_user_to_roster(room_jid, nick, show, role, ji)
			else:
				actual_role = self.get_role(room_jid, iter)
				if role != actual_role:
					self.remove_user(room_jid, nick)
					self.add_user_to_roster(room_jid, nick, show, role, ji)
				else:
					img = self.plugin.roster.pixbufs[show]
					model.set_value(iter, 0, img)
					model.set_value(iter, 3, show)
	
	def set_subject(self, room_jid, subject):
		self.subjects[room_jid] = subject
		self.xml.get_widget('subject_entry').set_text(subject)

	def on_set_button_clicked(self, widget):
		room_jid = self.get_active_jid()
		subject = self.xml.get_widget('subject_entry').get_text()
		gajim.connections[self.account].send_gc_subject(room_jid, subject)

	def on_message_textview_key_press_event(self, widget, event):
		"""When a key is pressed:
		if enter is pressed without the shit key, message (if not empty) is sent
		and printed in the conversation. Tab does autocompete in nickames"""
		jid = self.get_active_jid()
		conversation_textview = self.xmls[jid].get_widget('conversation_textview')
		if event.hardware_keycode == 23: # TAB
			if (event.state & gtk.gdk.CONTROL_MASK) and \
				(event.state & gtk.gdk.SHIFT_MASK): # CTRL + SHIFT + TAB  
				self.notebook.emit('key_press_event', event)
			elif event.state & gtk.gdk.CONTROL_MASK: # CTRL + TAB
				self.notebook.emit('key_press_event', event)
			else:
				room_jid = self.get_active_jid()
				list_nick = self.get_nick_list(room_jid)
				message_buffer = widget.get_buffer()
				start_iter = message_buffer.get_start_iter()
				cursor_position = message_buffer.get_insert()
				end_iter = message_buffer.get_iter_at_mark(cursor_position)
				text = message_buffer.get_text(start_iter, end_iter, 0)
				if not text:
					return False
				splitted_text = text.split()
				begin = splitted_text[-1] # begining of the latest word we typed
				for nick in list_nick:
					if nick.find(begin) == 0: # the word is the begining of a nick
						if len(splitted_text) == 1: # This is the 1st word of the line
							add = ': '
						else:
							add = ' '
						message_buffer.insert_at_cursor(nick[len(begin):] + add)
						return True
		elif event.keyval == gtk.keysyms.Page_Down: # PAGE DOWN
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE DOWN
				self.notebook.emit('key_press_event', event)
			elif event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE DOWN
				conversation_textview.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Page_Up: # PAGE UP
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE UP
				self.notebook.emit('key_press_event', event)
			elif event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE UP
				conversation_textview.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Return or \
			event.keyval == gtk.keysyms.KP_Enter: # ENTER
			if (event.state & gtk.gdk.SHIFT_MASK):
				return False
			message_buffer = widget.get_buffer()
			start_iter = message_buffer.get_start_iter()
			end_iter = message_buffer.get_end_iter()
			txt = message_buffer.get_text(start_iter, end_iter, 0)
			if txt != '':
				room_jid = self.get_active_jid()
				gajim.connections[self.account].send_gc_message(room_jid, txt)
				message_buffer.set_text('', -1)
				widget.grab_focus()
			return True
		return False

	def print_conversation(self, text, room_jid, contact = '', tim = None):
		"""Print a line in the conversation :
		if contact is set : it's a message from someone
		if contact is not set : it's a message from the server"""
		other_tags_for_name = []
		if contact:
			if contact == self.nicks[room_jid]:
				kind = 'outgoing'
			else:
				kind = 'incoming'
		else:
			kind = 'status'

		if kind == 'incoming' and self.nicks[room_jid].lower() in\
			text.lower().split():
			other_tags_for_name.append('bold')

		chat.Chat.print_conversation_line(self, text, room_jid, kind, contact, tim, \
			other_tags_for_name)

	def kick(self, widget, room_jid, nick):
		"""kick a user"""
		gajim.connections[self.account].gc_set_role(room_jid, nick, 'none')

	def grant_voice(self, widget, room_jid, nick):
		"""grant voice privilege to a user"""
		gajim.connections[self.account].gc_set_role(room_jid, nick, 'participant')

	def revoke_voice(self, widget, room_jid, nick):
		"""revoke voice privilege to a user"""
		gajim.connections[self.account].gc_set_role(room_jid, nick, 'visitor')

	def grant_moderator(self, widget, room_jid, nick):
		"""grant moderator privilege to a user"""
		gajim.connections[self.account].gc_set_role(room_jid, nick, 'moderator')

	def revoke_moderator(self, widget, room_jid, nick):
		"""revoke moderator privilege to a user"""
		gajim.connections[self.account].gc_set_role(room_jid, nick, 'participant')

	def ban(self, widget, room_jid, jid):
		"""ban a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid, \
			'outcast')

	def grant_membership(self, widget, room_jid, jid):
		"""grant membership privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid, \
			'member')

	def revoke_membership(self, widget, room_jid, jid):
		"""revoke membership privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid, \
			'none')

	def grant_admin(self, widget, room_jid, jid):
		"""grant administrative privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid, 'admin')

	def revoke_admin(self, widget, room_jid, jid):
		"""revoke administrative privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid, \
			'member')

	def grant_owner(self, widget, room_jid, jid):
		"""grant owner privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid, 'owner')

	def revoke_owner(self, widget, room_jid, jid):
		"""revoke owner privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid, 'admin')

	def on_info(self, widget, jid):
		"""Call vcard_information_window class to display user's information"""
		if not self.plugin.windows[self.account]['infos'].has_key(jid):
			self.plugin.windows[self.account]['infos'][jid] = \
				dialogs.Vcard_information_window(jid, self.plugin, self.account, \
					True)
			gajim.connections[self.account].request_vcard(jid)
			#FIXME: maybe use roster.on_info above?
			
			#FIXME: we need the resource but it's not saved
			#self.plugin.send('ASK_OS_INFO', self.account, jid, resource)

	def mk_menu(self, room_jid, event, iter):
		"""Make user's popup menu"""
		model = self.list_treeview[room_jid].get_model()
		nick = model.get_value(iter, 1)
		jid = model.get_value(iter, 2)
		
		menu = gtk.Menu()
		item = gtk.MenuItem(_('Privileges'))
		menu.append(item)
		
		sub_menu = gtk.Menu()
		item.set_submenu(sub_menu)
		item = gtk.MenuItem(_('Kick'))
		sub_menu.append(item)
		item.connect('activate', self.kick, room_jid, nick)
		item = gtk.MenuItem(_('Grant voice'))
		sub_menu.append(item)
		item.connect('activate', self.grant_voice, room_jid, nick)
		item = gtk.MenuItem(_('Revoke voice'))
		sub_menu.append(item)
		item.connect('activate', self.revoke_voice, room_jid, nick)
		item = gtk.MenuItem(_('Grant moderator'))
		sub_menu.append(item)
		item.connect('activate', self.grant_moderator, room_jid, nick)
		item = gtk.MenuItem(_('Revoke moderator'))
		sub_menu.append(item)
		item.connect('activate', self.revoke_moderator, room_jid, nick)
		if jid:
			item = gtk.MenuItem()
			sub_menu.append(item)

			item = gtk.MenuItem(_('Ban'))
			sub_menu.append(item)
			item.connect('activate', self.ban, room_jid, jid)
			item = gtk.MenuItem(_('Grant membership'))
			sub_menu.append(item)
			item.connect('activate', self.grant_membership, room_jid, jid)
			item = gtk.MenuItem(_('Revoke membership'))
			sub_menu.append(item)
			item.connect('activate', self.revoke_membership, room_jid, jid)
			item = gtk.MenuItem(_('Grant admin'))
			sub_menu.append(item)
			item.connect('activate', self.grant_admin, room_jid, jid)
			item = gtk.MenuItem(_('Revoke admin'))
			sub_menu.append(item)
			item.connect('activate', self.revoke_admin, room_jid, jid)
			item = gtk.MenuItem(_('Grant owner'))
			sub_menu.append(item)
			item.connect('activate', self.grant_owner, room_jid, jid)
			item = gtk.MenuItem(_('Revoke owner'))
			sub_menu.append(item)
			item.connect('activate', self.revoke_owner, room_jid, jid)

			item = gtk.MenuItem()
			menu.append(item)

			item = gtk.MenuItem(_('Information'))
			menu.append(item)
			item.connect('activate', self.on_info, jid)
		
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def remove_tab(self, room_jid):
		if time.time() - self.last_message_time[room_jid] < 2:
			dialog = dialogs.Confirmation_dialog(_('You received a message in the room %s in the last two seconds.\nDo you still want to close this tab?') % \
				room_jid.split('@')[0])
			if dialog.get_response() != gtk.RESPONSE_YES:
				return

		chat.Chat.remove_tab(self, room_jid, 'gc')
		if len(self.xmls) > 0:
			gajim.connections[self.account].send_gc_status(self.nicks[room_jid], \
				room_jid, 'offline', 'offline')
			del self.nicks[room_jid]
			del self.list_treeview[room_jid]
			del self.subjects[room_jid]

	def new_group(self, room_jid, nick):
		self.names[room_jid] = room_jid.split('@')[0]
		self.xmls[room_jid] = gtk.glade.XML(GTKGUI_GLADE, 'gc_vbox', APP)
		self.childs[room_jid] = self.xmls[room_jid].get_widget('gc_vbox')
		chat.Chat.new_tab(self, room_jid)
		self.nicks[room_jid] = nick
		self.subjects[room_jid] = ''
		self.list_treeview[room_jid] = self.xmls[room_jid].\
			get_widget('list_treeview')

		#status_image, nickname, real_jid, status
		store = gtk.TreeStore(gtk.Image, str, str, str)
		column = gtk.TreeViewColumn('contacts')
		renderer_image = cell_renderer_image.CellRendererImage()
		renderer_image.set_property('width', 20)
		column.pack_start(renderer_image, expand = False)
		column.add_attribute(renderer_image, 'image', 0)
		renderer_text = gtk.CellRendererText()
		column.pack_start(renderer_text, expand = True)
		column.add_attribute(renderer_text, 'text', 1)

		self.list_treeview[room_jid].append_column(column)
		self.list_treeview[room_jid].set_model(store)
		
		# workaround to avoid gtk arrows to be shown
		column = gtk.TreeViewColumn() # 2nd COLUMN
		renderer = gtk.CellRendererPixbuf()
		column.pack_start(renderer, expand = False)
		self.list_treeview[room_jid].append_column(column)
		column.set_visible(False)
		self.list_treeview[room_jid].set_expander_column(column)

		self.redraw_tab(room_jid)
		self.show_title()
	
	def on_groupchat_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			widget.get_toplevel().destroy()

	def on_list_treeview_button_press_event(self, widget, event):
		"""popup user's group's or agent menu"""
		if event.type == gtk.gdk.BUTTON_PRESS:
			if event.button == 3: # right click
				try:
					path, column, x, y = widget.get_path_at_pos(int(event.x), \
						int(event.y))
				except TypeError:
					widget.get_selection().unselect_all()
					return False
				model = widget.get_model()
				iter = model.get_iter(path)
				if len(path) == 2:
					room_jid = self.get_active_jid()
					self.mk_menu(room_jid, event, iter)
				return True
			if event.button == 1: # left click
				try:
					path, column, x, y = widget.get_path_at_pos(int(event.x), \
						int(event.y))
				except TypeError:
					widget.get_selection().unselect_all()
					return False

				model = widget.get_model()
				iter = model.get_iter(path)
				status = model.get_value(iter, 3) # if no status: it's a group
				if not status:
					if x < 20: # first cell in 1st column (the arrow SINGLE clicked)
						if (widget.row_expanded(path)):
							widget.collapse_row(path)
						else:
							widget.expand_row(path, False)
			
			#FIXME: should popup chat window for GC contact DOUBLE clicked
			# also chat [in contect menu]
		return False

	def on_list_treeview_key_press_event(self, widget, event):
		if event.type == gtk.gdk.KEY_RELEASE:
			if event.keyval == gtk.keysyms.Escape:
				widget.get_selection().unselect_all()
		return False

	def on_list_treeview_row_activated(self, widget, path, col=0):
		"""When an iter is double clicked: open the chat window"""
		model = widget.get_model()
		iter = model.get_iter(path)
		if len(path) == 1:
			if (widget.row_expanded(path)):
				widget.collapse_row(path)
			else:
				widget.expand_row(path, False)

	def on_list_treeview_row_expanded(self, widget, iter, path):
		"""When a row is expanded: change the icon of the arrow"""
		model = widget.get_model()
		model.set_value(iter, 0, self.plugin.roster.pixbufs['opened'])
	
	def on_list_treeview_row_collapsed(self, widget, iter, path):
		"""When a row is collapsed: change the icon of the arrow"""
		model = widget.get_model()
		model.set_value(iter, 0, self.plugin.roster.pixbufs['closed'])
