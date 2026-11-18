# Connecting an XMPP client

[Back to README](../README.md) · [HTTP API](http-api.md)

This document describes the gallery implementation in this repository. XMPP
carries account verification and chat messages; HTTPS carries gallery API calls
and media. The gallery logs in as a regular XMPP account to send codes. It is not
an XMPP external component or a XEP-0363 upload service.

## 1. Find the gallery

A client may accept an explicitly configured base URL or use Xabber's discovery
convention. Query the user's XMPP server with XEP-0030 `disco#info` and look for an
XEP-0128 extended data form with this form type and URL field:

```xml
<iq type="get" to="example.com" id="gallery-disco">
  <query xmlns="http://jabber.org/protocol/disco#info"/>
</iq>
```

The relevant part of the server's response is:

```xml
<x xmlns="jabber:x:data" type="result">
  <field var="FORM_TYPE" type="hidden">
    <value>urn:xabber:http:url</value>
  </field>
  <field var="urn:xabber:http:url:mediagallery">
    <value>https://gallery.example.com/api/</value>
  </field>
</x>
```

The XMPP server administrator must arrange this advertisement. **The gallery does
not publish discovery data or configure your XMPP server.** The exact server
module/configuration depends on your server; this repository supplies neither an
ejabberd nor a Prosody module for it.

Treat the advertised value as the base to which `v1/` is appended. The default
Django route is `/api/v1/`, so advertise `https://gallery.example.com/api/`, with a
trailing slash. Only advertise a different path if your proxy maps it accordingly.
Use trusted HTTPS endpoints and do not send gallery tokens to arbitrary URLs from
messages. This discovery convention is Xabber-specific, not a standard upload
feature advertisement.

## 2. Request an XMPP verification code

Connect to XMPP first and install your stanza handler **before** the HTTP request.
Use your full, currently connected JID for IQ delivery, so the server can route the
IQ to the correct resource. Keep both the full and normalized bare JID.

```sh
GALLERY_BASE='https://gallery.example.com/api/'
curl --fail-with-body "${GALLERY_BASE}v1/account/xmpp_code_request/" \
  -H 'Content-Type: application/json' \
  --data '{"jid":"alice@example.com/desktop","type":"iq"}'
```

HTTP 201 (illustrative values):

```json
{"request_id":"dc55238c-57fd-4a4b-95f2-c027991702c6","api_jid":"gallery-bot@example.com/gallery"}
```

Delivery runs in a background thread. HTTP 201 means the request was accepted,
not that a stanza reached the user. Buffer candidate stanzas if delivery races the
HTTP response, then correlate their stanza `id` with `request_id` and validate the
sender against the expected service JID (`api_jid`, ideally also trusted configuration).
Never automatically exchange an unrelated or unsolicited verification code.

## 3. Read the verification stanza

With `type: "iq"`, the gallery sends an IQ of type `get` containing an HTTP-auth
confirmation element (XEP-0070 namespace):

```xml
<iq type="get" from="gallery-bot@example.com/gallery"
    to="alice@example.com/desktop"
    id="dc55238c-57fd-4a4b-95f2-c027991702c6">
  <confirm xmlns="http://jabber.org/protocol/http-auth"
           id="123456"
           url="https://gallery.example.com/api/v1/account/xmpp_code_request/xmpp_auth"/>
</iq>
```

Read the numeric code from **`confirm/@id`**, not the outer IQ `id`. Acknowledge
handled IQ requests with a normal IQ result, preserving the request ID and
addressing the sender. The gallery does not wait for that result; the code is
exchanged over HTTP.

The `confirm/@url` above reflects the current implementation's relative URL
construction. It is **not the authentication endpoint**. Build the endpoint from
your trusted gallery base and `v1/account/xmpp_auth/` instead of following this URL.

If `type` is omitted or is `message`, the gallery sends a `chat` message with body
`Verification code is 123456` and the same `confirm` element. A user can enter that
code manually. IQ delivery to a bare JID is not reliable; prefer a connected full JID.

## 4. Exchange the code for an HTTP token

Use the **bare JID**, even when the request used a full JID. This endpoint looks up
the stored username directly. Codes expire after 90 seconds by default and are
deleted after successful exchange.

```sh
curl --fail-with-body "${GALLERY_BASE}v1/account/xmpp_auth/" \
  -H 'Content-Type: application/json' \
  --data '{"jid":"alice@example.com","code":123456,"client":"Example Client","device":"Desktop"}'
```

HTTP 201:

```json
{"token":"<bearer-token>","expires":"2026-11-19T12:00:00Z"}
```

Store the token using the client's secure credential storage. Send it only in the
`Authorization` header over HTTPS. Honor `expires` and repeat verification when a
new token is needed; no refresh-token endpoint exists. See [Operations](operations.md)
for the current server-side expiration limitation.

For the remaining curl examples, set `TOKEN` locally to the returned value without
committing it or including it in logs. Angle-bracket values are placeholders.

## 5. Check quota and deduplication (optional)

Compute the file's SHA-1 hex digest and exact byte size. The slot endpoint is a
quota/deduplication check, **not a presigned upload URL**:

```sh
curl --fail-with-body --get "${GALLERY_BASE}v1/files/slot/" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode 'name=hello.txt' \
  --data-urlencode 'size=6' \
  --data-urlencode 'hash=f572d396fae9206628714fb2ce00f72e94f2258f'
```

If the content is absent, HTTP 200 contains only quota data:

```json
{"quota":104857600,"used":0}
```

Upload the bytes in the next step. If the content exists, HTTP 200 contains a full
file response, including `file` and `hash`, and creates a **new user file record**
and public link. You may reuse the returned URL without uploading again. This GET
therefore has side effects: do not poll it, prefetch it, or automatically retry it
as a read-only operation. Its serializer has no context parameter, so the created
record uses the default `file` context. Upload directly for avatars/voice and other
contexts when those semantics are needed.

The SHA-1 hash is the service's deduplication identifier, not an end-to-end integrity
or encryption guarantee. A successful slot check does not reserve quota or storage.

## 6. Upload bytes

Create a small test file containing `hello` followed by a newline:

```sh
printf 'hello\n' > hello.txt
curl --fail-with-body "${GALLERY_BASE}v1/files/upload/" \
  -H "Authorization: Bearer $TOKEN" \
  -F 'file=@hello.txt;type=text/plain' \
  -F 'size=6' \
  -F 'media_type=text/plain' \
  -F 'context=file'
```

Let your HTTP library generate the multipart boundary; do not manually set
`Content-Type: multipart/form-data`. The server computes the hash from the bytes.
Use the actual byte size; prefer omitting `size` over supplying an inaccurate one.

HTTP 201 (timestamps, IDs, and link title are illustrative):

```json
{
  "id":42,
  "size":6,
  "media_type":"text/plain",
  "name":"hello.txt",
  "slot_id":"AbCdEf123456",
  "created_at":"2026-11-18T12:00:00Z",
  "file":"https://gallery.example.com/media/AbCdEf123456/hello.txt",
  "hash":"f572d396fae9206628714fb2ce00f72e94f2258f",
  "used":6,
  "quota":104857600,
  "context":"file"
}
```

`used` and `quota` are top-level byte counts, not a nested quota object. Image/video
responses may include a `thumbnail` object; avatar responses may also include a
`thumbnails` array. Generation is asynchronous, so a returned thumbnail URL can
briefly return 404. Use bounded retries rather than assuming it exists immediately.

For voice files use `context=voice`, a suitable MIME type (Xabber clients may use a
`+voice` suffix), and optional JSON `metadata`, such as duration and waveform data.
The gallery stores metadata; clients agree on its meaning. For avatars use
`context=avatar` and an image MIME type. Supported contexts are `file`, `avatar`,
`voice`, `gif`, and `call`.

## 7. Share the returned file URL over XMPP

The gallery does not send attachments to other users. Your client sends the
returned `file` URL in a chat message. This baseline works with clients that can
open HTTPS links:

```xml
<message to="bob@example.net" type="chat" id="attachment-1">
  <body>https://gallery.example.com/media/AbCdEf123456/hello.txt</body>
</message>
```

Xabber clients can additionally use custom file-sharing references. The following
shows the payload shape; implement the receiving client's reference/offset rules
before adding captions or combining multiple attachments:

```xml
<message to="bob@example.net" type="chat" id="attachment-2">
  <body>https://gallery.example.com/media/AbCdEf123456/hello.txt</body>
  <reference xmlns="https://xabber.com/protocol/references" type="mutable">
    <file-sharing xmlns="https://xabber.com/protocol/files">
      <file>
        <media-type>text/plain</media-type>
        <name>hello.txt</name>
        <size>6</size>
      </file>
      <sources>
        <uri>https://gallery.example.com/media/AbCdEf123456/hello.txt</uri>
      </sources>
    </file-sharing>
  </reference>
</message>
```

This XML is a client convention, not an endpoint validated by the gallery. The
HTTP service does not implement message parsing, reference offsets, or client UI.
It also does not encrypt files: if your client needs encrypted attachments, it must
handle encryption, keys, and compatible message metadata itself.

## 8. List, remove, and sign out

```sh
curl --fail-with-body "${GALLERY_BASE}v1/files/?contexts=file" \
  -H "Authorization: Bearer $TOKEN"

# Replace 42 with the uploaded file's actual id.
curl --fail-with-body -X DELETE "${GALLERY_BASE}v1/files/" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"id":42}'
```

Deletion removes the user's file record/link, not copies held by recipients or
other users' links to deduplicated content. Public media URLs require no bearer
token: anyone with the URL can download the file until its link is removed.

For sign-out, remove the local token from secure storage. The API exposes token
listing/deletion, but its current views do not filter token objects to the caller;
restrict those routes until ownership checks are implemented. See [Operations](operations.md).
