import asks.response_objects

def test_response_repr():
    r = asks.response_objects.Response('ascii', status_code=200, reason_phrase="Meh")
    assert repr(r) == '<Response 200 Meh>'
