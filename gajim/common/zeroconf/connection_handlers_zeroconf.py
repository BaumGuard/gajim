##
## Copyright (C) 2006 Gajim Team
##
## Contributors for this file:
##      - Yann Leboulanger <asterix@lagaule.org>
##      - Nikos Kouremenos <nkour@jabber.org>
##      - Dimitur Kirov <dkirov@gmail.com>
##      - Travis Shirk <travis@pobox.com>
## - Stefan Bethge <stefan@lanpartei.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

import nbxmpp

from gajim.common import app
from gajim.common.commands import ConnectionCommands
from gajim.common.protocol.bytestream import ConnectionSocks5BytestreamZeroconf
from gajim.common.connection_handlers_events import ZeroconfMessageReceivedEvent

import logging
log = logging.getLogger('gajim.c.z.connection_handlers_zeroconf')

STATUS_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
        'invisible']
# kind of events we can wait for an answer
AGENT_REMOVED = 'agent_removed'

from gajim.common import connection_handlers

class ConnectionVcard(connection_handlers.ConnectionVcard):
    def add_sha(self, p, *args):
        return p

    def add_caps(self, p):
        return p

    def request_vcard(self, *args):
        pass

    def send_vcard(self, *args):
        pass


class ConnectionHandlersZeroconf(ConnectionVcard,
ConnectionSocks5BytestreamZeroconf, ConnectionCommands,
connection_handlers.ConnectionPEP, connection_handlers.ConnectionHandlersBase,
connection_handlers.ConnectionJingle):
    def __init__(self):
        ConnectionVcard.__init__(self)
        ConnectionSocks5BytestreamZeroconf.__init__(self)
        ConnectionCommands.__init__(self)
        connection_handlers.ConnectionJingle.__init__(self)
        connection_handlers.ConnectionHandlersBase.__init__(self)

    def _messageCB(self, ip, con, msg):
        """
        Called when we receive a message
        """
        log.debug('Zeroconf MessageCB')
        app.nec.push_incoming_event(ZeroconfMessageReceivedEvent(None,
            conn=self, stanza=msg, ip=ip))
        return

    def store_metacontacts(self, tags):
        """
        Fake empty method
        """
        # serverside metacontacts are not supported with zeroconf
        # (there is no server)
        pass

    def _DiscoverItemsGetCB(self, con, iq_obj):
        log.debug('DiscoverItemsGetCB')

        if not self.connection or self.connected < 2:
            return

        if self.commandItemsQuery(con, iq_obj):
            raise nbxmpp.NodeProcessed
        node = iq_obj.getTagAttr('query', 'node')
        if node is None:
            result = iq_obj.buildReply('result')
            self.connection.send(result)
            raise nbxmpp.NodeProcessed
        if node==nbxmpp.NS_COMMANDS:
            self.commandListQuery(con, iq_obj)
            raise nbxmpp.NodeProcessed
