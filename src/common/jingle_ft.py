# -*- coding:utf-8 -*-
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##


"""
Handles  Jingle File Transfer (XEP 0234)
"""

import hashlib
import gajim
import xmpp
from jingle_content import contents, JingleContent
from jingle_transport import *
from common import helpers
from common.socks5 import Socks5ReceiverClient, Socks5SenderClient
from common.connection_handlers_events import FileRequestReceivedEvent
import threading
import logging
from jingle_ftstates import *
log = logging.getLogger('gajim.c.jingle_ft')

STATE_NOT_STARTED = 0
STATE_INITIALIZED = 1
# We send the candidates and we are waiting for a reply
STATE_CAND_SENT = 2
# We received the candidates and we are waiting to reply
STATE_CAND_RECEIVED = 3
# We have sent and received the candidates
# This also includes any candidate-error received or sent
STATE_CAND_SENT_AND_RECEIVED = 4
STATE_TRANSPORT_REPLACE = 5
# We are transfering the file
STATE_TRANSFERING = 6


class JingleFileTransfer(JingleContent):
    def __init__(self, session, transport=None, file_props=None,
    use_security=False):
        JingleContent.__init__(self, session, transport)

        log.info("transport value: %s" % transport)

        # events we might be interested in
        self.callbacks['session-initiate'] += [self.__on_session_initiate]
        self.callbacks['session-initiate-sent'] += [self.__on_session_initiate_sent]
        self.callbacks['content-add'] += [self.__on_session_initiate]
        self.callbacks['session-accept'] += [self.__on_session_accept]
        self.callbacks['session-terminate'] += [self.__on_session_terminate]        
        self.callbacks['session-info'] += [self.__on_session_info]
        self.callbacks['transport-accept'] += [self.__on_transport_accept]
        self.callbacks['transport-replace'] += [self.__on_transport_replace]
        self.callbacks['session-accept-sent'] += [self.__transport_setup]
        # fallback transport method
        self.callbacks['transport-reject'] += [self.__on_transport_reject]
        self.callbacks['transport-info'] += [self.__on_transport_info]
        self.callbacks['iq-result'] += [self.__on_iq_result]

        self.use_security = use_security

        self.file_props = file_props
        if file_props is None:
            self.weinitiate = False
        else:
            self.weinitiate = True

        if self.file_props is not None:
            self.file_props['sender'] = session.ourjid
            self.file_props['receiver'] = session.peerjid
            self.file_props['session-type'] = 'jingle'
            self.file_props['session-sid'] = session.sid
            self.file_props['transfered_size'] = []

        log.info("FT request: %s" % file_props)

        if transport is None:
            self.transport = JingleTransportSocks5()
        self.transport.set_connection(session.connection)
        self.transport.set_file_props(self.file_props)
        self.transport.set_our_jid(session.ourjid)
        log.info('ourjid: %s' % session.ourjid)

        if self.file_props is not None:
            self.file_props['sid'] = self.transport.sid

        self.session = session
        self.media = 'file'
        self.nominated_cand = {}
        if gajim.contacts.is_gc_contact(session.connection.name, 
                                        session.peerjid):
            roomjid = session.peerjid.split('/')[0]
            dstaddr = hashlib.sha1('%s%s%s' % (self.file_props['sid'],
                                     session.ourjid,
                                     roomjid)).hexdigest()
            self.file_props['dstaddr'] = dstaddr
        self.state = STATE_NOT_STARTED
        self.states = {STATE_INITIALIZED   : StateInitialized(self),
                       STATE_CAND_SENT     : StateCandSent(self),
                       STATE_CAND_RECEIVED : StateCandReceived(self),
                       STATE_TRANSFERING   : StateTransfering(self),
                   STATE_TRANSPORT_REPLACE : StateTransportReplace(self),
              STATE_CAND_SENT_AND_RECEIVED : StateCandSentAndRecv(self)
                      }

    def __state_changed(self, nextstate, args=None):
        # Executes the next state action and sets the next state
        st = self.states[nextstate]
        st.action(args)
        self.state = nextstate

    def __on_session_initiate(self, stanza, content, error, action):
        gajim.nec.push_incoming_event(FileRequestReceivedEvent(None,
            conn=self.session.connection, stanza=stanza, jingle_content=content,
            FT_content=self))
        self._listen_host() 
        # Delete this after file_props refactoring this shouldn't be necesary
        self.session.file_hash = self.file_props['hash']
        self.session.hash_algo = self.file_props['algo']

    def __on_session_initiate_sent(self, stanza, content, error, action):
        # Calculate file_hash in a new thread
        # if we haven't sent the hash already.
        if 'hash' not in self.file_props:
            self.hashThread = threading.Thread(target=self.__send_hash)
            self.hashThread.start()
        
    def __send_hash(self):
        # Send hash in a session info
        checksum = xmpp.Node(tag='checksum',  
                             payload=[xmpp.Node(tag='file',
                                 payload=[self._calcHash()])])
        checksum.setNamespace(xmpp.NS_JINGLE_FILE_TRANSFER)
        self.session.__session_info(checksum )
    

    def _calcHash(self):
        # Caculates the hash and returns a xep-300 hash stanza
        if self.session.hash_algo == None:
            return
        try:
            file_ = open(self.file_props['file-name'], 'r')
        except:
            # can't open file
            return
        h = xmpp.Hashes()
        hash_ = h.calculateHash(self.session.hash_algo, file_)
        # DEBUG
        #hash_ = '1294809248109223'
        if not hash_:
            # Hash alogrithm not supported
            return
        self.file_props['hash'] = hash_
        h.addHash(hash_, self.session.hash_algo)
        return h
                
    def __on_session_accept(self, stanza, content, error, action):
        log.info("__on_session_accept")
        con = self.session.connection
        security = content.getTag('security')
        if not security: # responder can not verify our fingerprint
            self.use_security = False


        if self.state == STATE_TRANSPORT_REPLACE:
            # We ack the session accept
            response = stanza.buildReply('result')
            response.delChild(response.getQuery())
            con.connection.send(response)
            # We send the file
            self.__state_changed(STATE_TRANSFERING)
            raise xmpp.NodeProcessed

        self.file_props['streamhosts'] = self.transport.remote_candidates
        for host in self.file_props['streamhosts']:
            host['initiator'] = self.session.initiator
            host['target'] = self.session.responder
            host['sid'] = self.file_props['sid']

        response = stanza.buildReply('result')
        response.delChild(response.getQuery())
        con.connection.send(response)

        if not gajim.socks5queue.get_file_props(
           self.session.connection.name, self.file_props['sid']):
            gajim.socks5queue.add_file_props(self.session.connection.name,
                self.file_props)
        fingerprint = None
        if self.use_security:
            fingerprint = 'client'
        if self.transport.type == TransportType.SOCKS5:
            gajim.socks5queue.connect_to_hosts(self.session.connection.name,
                self.file_props['sid'], self.on_connect,
                self._on_connect_error, fingerprint=fingerprint,
                receiving=False)
            return
        self.__state_changed(STATE_TRANSFERING)
        raise xmpp.NodeProcessed

    def __on_session_terminate(self, stanza, content, error, action):
        log.info("__on_session_terminate")

    def __on_session_info(self, stanza, content, error, action):
        pass
        
    def __on_transport_accept(self, stanza, content, error, action):
        log.info("__on_transport_accept")

    def __on_transport_replace(self, stanza, content, error, action):
        log.info("__on_transport_replace")

    def __on_transport_reject(self, stanza, content, error, action):
        log.info("__on_transport_reject")

    def __on_transport_info(self, stanza, content, error, action):
        log.info("__on_transport_info")

        if content.getTag('transport').getTag('candidate-error'):
            self.nominated_cand['peer-cand'] = False
            if self.state == STATE_CAND_SENT:
                if not self.nominated_cand['our-cand'] and \
                   not self.nominated_cand['peer-cand']:
                    if not self.weinitiate:
                        return
                    self.__state_changed(STATE_TRANSPORT_REPLACE)
                else:
                    response = stanza.buildReply('result')
                    response.delChild(response.getQuery())
                    self.session.connection.connection.send(response)
                    self.__state_changed(STATE_TRANSFERING)
                    raise xmpp.NodeProcessed
            else:
                args = {'candError' : True}
                self.__state_changed(STATE_CAND_RECEIVED, args)
            return

        if content.getTag('transport').getTag('activated'):
            self.state = STATE_TRANSFERING
            jid = gajim.get_jid_without_resource(self.session.ourjid)
            gajim.socks5queue.send_file(self.file_props,
                self.session.connection.name, 'client')
            return

        args = {'content' : content,
                'sendCand' : False}
        if self.state == STATE_CAND_SENT:
            self.__state_changed(STATE_CAND_SENT_AND_RECEIVED, args)
            response = stanza.buildReply('result')
            response.delChild(response.getQuery())
            self.session.connection.connection.send(response)
            self.__state_changed(STATE_TRANSFERING)
            raise xmpp.NodeProcessed
        else:
            self.__state_changed(STATE_CAND_RECEIVED, args)



    def __on_iq_result(self, stanza, content, error, action):
        log.info("__on_iq_result")

        if self.state == STATE_NOT_STARTED:
            self.__state_changed(STATE_INITIALIZED)
        elif self.state == STATE_CAND_SENT_AND_RECEIVED:
            if not self.nominated_cand['our-cand'] and \
            not self.nominated_cand['peer-cand']:
                if not self.weinitiate:
                    return
                self.__state_changed(STATE_TRANSPORT_REPLACE)
                return
            # initiate transfer
            self.__state_changed(STATE_TRANSFERING)
            
    def __transport_setup(self, stanza=None, content=None, error=None,
    action=None):
        # Sets up a few transport specific things for the file transfer
            
        if self.transport.type == TransportType.IBB:
            # No action required, just set the state to transfering
            self.state = STATE_TRANSFERING
            

    def on_connect(self, streamhost):
        """
        send candidate-used stanza
        """
        log.info('send_candidate_used')
        if streamhost is None:
            return
        args = {'streamhost' : streamhost,
                'sendCand'   : True}

        self.nominated_cand['our-cand'] = streamhost
        self.__sendCand(args)

    def _on_connect_error(self, sid):
        log.info('connect error, sid=' + sid)
        args = {'candError' : True,
                'sendCand'  : True}
        self.__sendCand(args)

    def __sendCand(self, args):
        if self.state == STATE_CAND_RECEIVED:
            self.__state_changed(STATE_CAND_SENT_AND_RECEIVED, args)
        else:
            self.__state_changed(STATE_CAND_SENT, args)

    def _store_socks5_sid(self, sid, hash_id):
        # callback from socsk5queue.start_listener
        self.file_props['hash'] = hash_id

    def _listen_host(self):

        receiver = self.file_props['receiver']
        sender = self.file_props['sender']
        sha_str = helpers.get_auth_sha(self.file_props['sid'], sender,
            receiver)
        self.file_props['sha_str'] = sha_str

        port = gajim.config.get('file_transfers_port')

        fingerprint = None
        if self.use_security:
            fingerprint = 'server'

        if self.weinitiate:
            listener = gajim.socks5queue.start_listener(port, sha_str,
                self._store_socks5_sid, self.file_props,
                fingerprint=fingerprint, type='sender')
        else:
            listener = gajim.socks5queue.start_listener(port, sha_str,
                self._store_socks5_sid, self.file_props,
                fingerprint=fingerprint, type='receiver')

        if not listener:
            # send error message, notify the user
            return
    def isOurCandUsed(self):
        '''
        If this method returns true then the candidate we nominated will be
        used, if false, the candidate nominated by peer will be used
        '''

        if self.nominated_cand['peer-cand'] == False:
            return True
        if self.nominated_cand['our-cand'] == False:
            return False

        peer_pr = int(self.nominated_cand['peer-cand']['priority'])
        our_pr = int(self.nominated_cand['our-cand']['priority'])

        if peer_pr != our_pr:
            return our_pr > peer_pr
        else:
            return self.weinitiate


def get_content(desc):
    return JingleFileTransfer

contents[xmpp.NS_JINGLE_FILE_TRANSFER] = get_content