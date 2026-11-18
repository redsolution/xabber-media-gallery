from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework import status

from gallery.api.models import EntityFile, WhiteList, BlackList, Token

import xmpp


def is_blacklisted_or_not_whitelisted(bare_jid: str, domain: str) -> bool:

    """ Check if a username or host is blacklisted or not whitelisted """

    # Retrieve the blacklist and split it if it exists
    black_list = BlackList.objects.filter(host=domain).first()

    white_list = WhiteList.objects.filter(host=domain).first()

    # Check if the full JID or just the host is in the blacklist
    if black_list:
        if black_list.all_users:
            return True
        elif black_list.users.exists() and bare_jid in black_list.get_users():
            return True

    # Check if the full JID or just the host is not in the whitelist
    if white_list and not white_list.all_users and white_list.users.exists():
        if bare_jid not in white_list.get_users():
            return True

    # If none of the above conditions are met, return False
    return False


def check_scope(token: Token, users: list, host: str, all_users=False) -> bool:
    scope = token.scope

    access = False

    if isinstance(users, str):
        users = [users]

    if scope:
        if scope == 'global':
            access = True

        elif scope == host:
            access = True

        elif ',' in scope:
            scope_list = {item.strip() for item in scope.split(',') if item.strip()}

            if all_users:
                # проверяем доступ к host
                access = host in scope_list

            else:
                input_users = set(users)

                # разделяем scope на JID и host
                scope_jids = {item for item in scope_list if '@' in item}
                scope_hosts = {item for item in scope_list if '@' not in item}

                def user_allowed(jid: str) -> bool:
                    # доступ если JID явно указан
                    if jid in scope_jids:
                        return True

                    # доступ если host пользователя есть в scope
                    try:
                        _, jid_host = jid.split('@', 1)
                    except ValueError:
                        return False

                    return jid_host in scope_hosts

                access = all(user_allowed(jid) for jid in input_users)

    if not access:
        raise PermissionDenied({
            'status': status.HTTP_403_FORBIDDEN,
            'error': 'Access denied'
        })


def send_code(
        sjid: str, password: str,
        code: str, srecipient: str,
        stanza_id: str,
        stanza_type: str, url: str) -> bool:

    """ Send verification code """

    # try, except for using threading
    try:
        jid = xmpp.protocol.JID(sjid)
        recipient = xmpp.protocol.JID(srecipient)
        cl = xmpp.Client(jid.getDomain(), debug=[])
        con = cl.connect()
        if not con:
            print('Error connecting to the XMPP server')
            return False
        auth = cl.auth(jid.getNode(), password, resource=jid.getResource())
        if not auth:
            print('Authentication error on XMPP server')
            return False
        if stanza_type == 'message':
            packet = xmpp.protocol.Message(recipient, 'Verification code is {}'.format(code),
                                           'chat', payload=[xmpp.protocol.Node('urn:xmpp:hints no-store')])
            if recipient.getResource():
                packet.addChild(name='private', namespace='urn:xmpp:carbons:2')
                packet.addChild(name='no-copy', namespace='urn:xmpp:hints')
        else:
            packet = xmpp.protocol.Iq(typ='get', to=recipient)

        packet.addChild(name='confirm', attrs={'id': code, 'url': url},
                        namespace='http://jabber.org/protocol/http-auth')
        packet.setAttr('id', stanza_id)
        cl.send(packet)
        cl.disconnect()
    except Exception as e:
        print(e)


def delete_files():
    # try, except for using threading
    try:
        EntityFile.objects.filter(mediafile=None).delete()
    except Exception as e:
        print(e)
