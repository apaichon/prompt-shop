import asyncio
import json
import httpx
import pytest
from prompt_shop_live.host import ToolHost
from prompt_shop_live.protocol import Setup
from prompt_shop_live.tools import BlockingTool,SCHEMAS
from tools.intent import Classifier,MODEL_REVISION

TOKEN="task10-synthetic-adapter-token-only-12345"


def classified(label):
    return {"schema_version":"intent-v1","intent":label,"confidence":.95,"margin":.8,"abstained":False,"reason":None,"model_revision":MODEL_REVISION}


def setup(): return Setup(type="setup",session_id="task10-fixture",language="en-US",turn_id="turn-0",tool_capability="x"*43)


@pytest.mark.asyncio
@pytest.mark.parametrize("label",["find_item","select_item","repeat_directions","out_of_scope"])
async def test_adk_blocking_tool_ack_and_labels_have_no_catalog_authority(label):
    events,requests=[],[]
    async def classify(request): return httpx.Response(200,json=classified(label))
    async def go(request):
        requests.append(request)
        envelope=json.loads(request.content)
        assert set(envelope)=={"session_id","turn_id","call_id","classification_attempt_id","args"}
        assert envelope['classification_attempt_id']==events[-1]['classification_attempt_id']
        assert request.headers['Authorization']=='Bearer '+setup().tool_capability
        # Explicit Go bridge fixture rejects a non-member route regardless of label.
        if request.url.path.endswith('get_product_route'):
            return httpx.Response(200,json={"error":{"code":"STALE_SELECTION"}})
        return httpx.Response(200,json={"candidates":[],"ambiguous":False})
    async def send(event): events.append(event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(go)) as client:
        host=ToolHost(setup(),send,Classifier(TOKEN,transport=httpx.MockTransport(classify)),client)
        host.begin('turn-1');tool=BlockingTool('classify_intent',host)
        declaration=tool._get_declaration()
        assert declaration.behavior.value=='BLOCKING'
        assert set(SCHEMAS)=={'classify_intent','search_catalog','get_product_route'}
        assert (await host.call('search_catalog',{'query':'synthetic item'}))['error']['code']=='CLASSIFICATION_REQUIRED'
        attempt=asyncio.create_task(tool.run_async(args={'text':'synthetic controlled request'},tool_context=None))
        while not events: await asyncio.sleep(.002)
        assert set(events[-1]['result'])=={'schema_version','intent','confidence','margin','abstained','reason','model_revision'}
        host.acknowledge({**events[-1],'turn_id':'turn-0'});await asyncio.sleep(.01)
        assert not attempt.done() and not requests
        host.acknowledge(events[-1]);assert (await attempt)['intent']==label
        assert (await host.call('get_product_route',{'product_id':'not-a-candidate','search_id':'unknown'}))['error']['code']=='STALE_SELECTION'
        assert len(requests)==1
        assert requests[0].url.host=='127.0.0.1' and requests[0].url.port==8002
        await host.close();assert not host.tasks


@pytest.mark.asyncio
async def test_stale_classification_is_cancelled_before_ack_or_catalog():
    gate=asyncio.Event();events=[]
    async def classify(request): await gate.wait();return httpx.Response(200,json=classified('find_item'))
    async def send(event): events.append(event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={}))) as client:
        host=ToolHost(setup(),send,Classifier(TOKEN,transport=httpx.MockTransport(classify)),client)
        host.begin('turn-1');tool=BlockingTool('classify_intent',host)
        task=asyncio.create_task(tool.run_async(args={'text':'synthetic'},tool_context=None));await asyncio.sleep(.01)
        host.begin('turn-2');gate.set()
        with pytest.raises(asyncio.CancelledError): await task
        assert not events and not host.classified and not host.tasks
        await host.close()


@pytest.mark.asyncio
async def test_unavailable_classifier_has_typed_abstention_and_required_ack():
    events=[]
    async def classify(request): raise httpx.ConnectError('synthetic failure')
    async def send(event): events.append(event);host.acknowledge(event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={}))) as client:
        host=ToolHost(setup(),send,Classifier(TOKEN,transport=httpx.MockTransport(classify)),client)
        host.begin('turn-1');tool=BlockingTool('classify_intent',host)
        result=await tool.run_async(args={'text':'synthetic'},tool_context=None)
        assert result['abstained'] and result['reason']=='error' and result['intent'] is None
        assert host.classified and host.ack.is_set() and not host.audio_allowed
        assert len(events)==1
        host.begin('turn-2')
        malformed=await tool.run_async(args={'text':'synthetic','url':'https://untrusted.example.test'},tool_context=None)
        assert malformed['error']['code']=='INVALID_REQUEST' and len(events)==1
        await host.close()
