"""Browser regression for drawing layers (requires requirements-dev.txt and Edge).

Start the existing Vite dev server, then run:
    python scripts/qa_drawing_layers.py --url http://127.0.0.1:5179/react

Uses the real editor component with a mocked drawing-project API; user projects
are never opened. Creates a temporary Vite entry and removes it on completion.
Browser plugin not available in the original QA run; Playwright fallback used.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', default='http://127.0.0.1:5179/react')
options = parser.parse_args()
(root / 'test-results').mkdir(exist_ok=True)
harness_path = root / 'frontend' / '.drawing-layers-qa.html'
harness = """<!doctype html><html><head><title>Nihilux Drawing QA</title><style>html,body,#root {margin:0;width:100%;height:100%;background:#242424;color:#eee} button,input {font:inherit} .full-drawing-editor{height:100vh!important}</style></head><body><div id="root"></div><script type="module">
import React from 'react';
import {createRoot} from 'react-dom/client';
import {FullDrawingEditor} from '/src/components/FullDrawingEditor.tsx';
import '/src/index.css'; import '/src/App.css'; import '/src/components/CanvasBoard.css';
window.qaErrors=[];
const onError=e=>{window.qaErrors.push(String(e));};
const onSave=async (png,data)=>{localStorage.setItem('qaDrawing',data);window.qaSaved=JSON.parse(data);window.qaPng=png;return true;};
createRoot(document.getElementById('root')).render(React.createElement(FullDrawingEditor,{shotId:'qa',width:640,height:360,artworkImage:'',boardBackgroundImage:'',codexImage:'',canvasColor:'#ffffff',disabled:false,onCancel:()=>{},onError,onSave}));
</script></body></html>"""
with harness_path.open('x', encoding='utf-8') as entry:
    entry.write(harness)
try:
    state={'saved':None}
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':950},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda e: errors.append(str(e)))
        page.on('console',lambda msg: errors.append(msg.text) if msg.type=='error' else None)
        page.route('**/api/shots/qa/drawing-project',lambda route: route.fulfill(json={'editor_data':state['saved']}))
        page.goto(options.url.rstrip('/') + '/.drawing-layers-qa.html')
        page.get_by_role('button',name='Save drawing',exact=True).wait_for()
        page.wait_for_function("!document.querySelector('.full-drawing-loading')")
        assert page.title()=='Nihilux Drawing QA'
        assert page.locator('vite-error-overlay').count()==0
        canvas=page.locator('canvas.upper-canvas')
        def stroke(x,y,dx=80):
            b=canvas.bounding_box(); page.mouse.move(b['x']+x,b['y']+y);page.mouse.down()
            page.mouse.move(b['x']+x+dx,b['y']+y+18,steps=12);page.mouse.up();page.wait_for_timeout(120)
        def save():
            page.get_by_role('button',name='Save drawing',exact=True).click()
            page.wait_for_function('window.qaSaved != null')
            result=page.evaluate('window.qaSaved')
            state['saved']=json.dumps(result)
            page.evaluate('window.qaSaved=null')
            return result
        def groups(doc):return [o for o in doc['canvas']['objects'] if o.get('storyboardDrawingLayer')]
        stroke(80,100);stroke(100,150);stroke(130,200)
        assert page.locator('.native-drawing-layer').count()==2
        initial=save(); assert len(groups(initial))==1 and len(groups(initial)[0]['objects'])==3
        first=groups(initial)[0]['storyboardId'];name=groups(initial)[0]['storyboardName']
        page.get_by_role('button',name='Undo',exact=True).click();page.wait_for_timeout(200)
        assert len(groups(save())[0]['objects'])==2
        page.get_by_role('button',name='Redo',exact=True).click();page.wait_for_timeout(200)
        assert len(groups(save())[0]['objects'])==3
        page.get_by_role('button',name='New layer',exact=True).click();stroke(260,130)
        assert page.locator('.native-drawing-layer').count()==3
        added=save(); assert [len(g['objects']) for g in groups(added)]==[3,1]
        page.locator('.native-layer-name').filter(has_text=name).click()
        page.get_by_role('button',name='Pen',exact=True).click();stroke(190,230)
        switched=save();assert [len(g['objects']) for g in groups(switched)]==[4,1]
        assert groups(switched)[0]['storyboardId']==first
        page.reload();page.wait_for_function("!document.querySelector('.full-drawing-loading')")
        assert page.locator('.native-drawing-layer').count()==3
        stroke(300,180)
        restored=save();assert len(groups(restored))==2 and [len(g['objects']) for g in groups(restored)]==[4,2]
        page.get_by_role('button',name='Eraser',exact=True).click();stroke(300,180,40)
        erased=save();assert len(groups(erased))==2 and groups(erased)[1]['objects'][-1]['globalCompositeOperation']=='destination-out'
        assert page.locator('.native-drawing-layer').count()==3
        layername=groups(erased)[1]['storyboardName']
        page.get_by_role('button',name='Lock '+layername,exact=True).click()
        stroke(400,220)
        assert page.evaluate('window.qaErrors.length')==1
        page.get_by_role('button',name='Unlock '+layername,exact=True).click()
        page.evaluate('window.qaErrors=[]')
        page.get_by_role('button',name='Pen',exact=True).click()
        stroke(400,220)
        restored=save();assert len(groups(restored)[1]['objects'])==4
        # A legacy v1 document with standalone paths remains editable and preserved.
        legacy=json.loads(json.dumps(initial)); legacy['canvas']['objects']=[initial['canvas']['objects'][0],*groups(initial)[0]['objects']]
        state['saved']=json.dumps(legacy)
        page.reload();page.wait_for_function("!document.querySelector('.full-drawing-loading')")
        assert page.locator('.native-drawing-layer').count()==4
        stroke(200,160)
        legacy_saved=save();assert len(legacy_saved['canvas']['objects'])==5 and len(groups(legacy_saved))==1
        state['saved']=json.dumps(restored)
        page.reload();page.wait_for_function("!document.querySelector('.full-drawing-loading')")
        assert not errors,errors
        assert page.evaluate('window.qaErrors')==[]
        page.screenshot(path=str(root/'test-results/drawing-layers.png'))
        (root/'test-results/drawing-qa-result.json').write_text(json.dumps({'status':'PASS','url':page.url,'viewport':'1440x950','checks':['three strokes share one layer','undo/redo per stroke','explicit new layer','switch layer then draw','save/reload preserves groups','draw after reload','eraser stays in layer','locked layer rejects stroke','legacy v1 document preserved','no page/console errors'],'saved':restored},indent=2),encoding='utf-8')
        browser.close()
    print('Drawing UI QA PASS')

finally:
    harness_path.unlink()
