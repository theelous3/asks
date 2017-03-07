import curio

from .req_structs import CaseInsensitiveDict as c_i_Dict

from .errors import RequestTimeout


class HttpParser:
    '''
    A class which parses request responses.
    '''
    def __init__(self, stream_obj):
        self.stream_obj = stream_obj

    async def parse_stream_headers(self, timeout=None):
        '''
        Parses the response status line and headers, returning when the end of
        the headers is reached. Implements a response timeout if one is set.
        '''
        req_dict = {'reason_phrase': None,
                    'status_code': '',
                    'http_version': None,
                    'headers': c_i_Dict(),
                    'errors': {},
                    'cookies': []
                    }

        try:
            if timeout:
                response_task = await curio.spawn(self.stream_obj.__anext__())
                try:
                    status_line = await curio.timeout_after(
                        timeout, response_task.join())
                except curio.TaskTimeout:
                    await response_task.cancel()
                    raise RequestTimeout
            else:
                status_line = await self.stream_obj.__anext__()
        except StopAsyncIteration:
            req_dict['errors']['ClosedEarly'] = 'Server closed the connection.'
            return req_dict
        status_line = status_line.decode('utf-8',
                                         errors='replace').strip().split(' ',
                                                                         2)
        try:
            req_dict['http_version'], \
             req_dict['status_code'], \
             req_dict['reason_phrase'] = status_line
        except ValueError:
            req_dict['errors']['InvalidFirstLine'] = status_line
            return req_dict

        async for hder_field in self.stream_obj:
            if not any(hder_field == x for x in (b'\r\n', b'\n')):
                hder_field = hder_field.decode('utf-8').strip().split(':', 1)

                try:
                    header, header_content = hder_field
                except ValueError:
                    break
                else:
                    if header.lower() == 'set-cookie':
                        req_dict['cookies'].append(header_content)
                    else:
                        req_dict['headers'][header] = header_content.lstrip()
            else:
                break

        return req_dict

    async def parse_body(self,
                         length=0,
                         callback=False,
                         chunked=False):
        '''
        Parses the response body, returning when the end of
        the body is reached, or if a callback is set, when that completes.
        '''
        if callback:
            await self._body_callback(callback)
            return

        body_total = b''
        if chunked:
            inside_chunk = False
            while True:
                chunk = await self.stream_obj.readline()
                if not chunk.strip():
                    break
                else:
                    if chunk.endswith(b'\r\n'):
                        if not inside_chunk:
                            inside_chunk = True
                            continue
                        else:
                            body_total += chunk.strip()
                            inside_chunk = False
                    else:
                        body_total += chunk
            return body_total.strip()
        else:
            readsize = 1024
            redd = 0
            while redd != length:
                if (length - redd) < readsize:
                    readsize = length - redd
                current_chunk = await self.stream_obj.read(readsize)
                body_total += current_chunk
                redd += len(current_chunk)

        return body_total.strip()

    async def _body_callback(self, func):
        '''
        A callback func to be supplied if the user wants to do something
        directly with the response body's stream.

        UNTESTED! Gut feeling says this will hang indefinitely. Do test!
        '''
        while True:
            bytechunk = await self.stream_obj.read(2048)
            if not bytechunk:
                break
            else:
                await func(bytechunk)
