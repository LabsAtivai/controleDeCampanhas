import threading
import os
from contextlib import contextmanager

import pandas as pd
import pytest
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server

from core.security import save_user
from db import avancos_api, crud
from tests.test_data_collection import metric


@contextmanager
def site(app):
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(10)
        server.server_close()


def login_ui(page, url):
    page.goto(url + '/login.html')
    page.get_by_label('E-mail', exact=True).fill('admin@example.test')
    page.get_by_label('Senha', exact=True).fill('Very-Strong-Test-Password')
    page.get_by_role('button', name='Entrar', exact=True).click()
    page.wait_for_url('**/dados.html')


@pytest.mark.browser
def test_browser_login_analysis_xss_mobile_and_operations(app, monkeypatch, tmp_path):
    save_user('admin@example.test', 'Very-Strong-Test-Password', 'admin')
    crud.atualiza_registros(pd.DataFrame([metric()]))
    payload = 'Cliente " onmouseover="window.__auditXss=1" data-x="'
    monkeypatch.setattr(avancos_api, 'cliente_da_conta', lambda account: payload)
    monkeypatch.setattr(avancos_api, 'total_por_cliente', lambda *args: {payload.lower(): 2})
    monkeypatch.setattr(avancos_api, 'status_por_cliente', lambda: {payload.lower(): 'verde'})
    monkeypatch.setattr(avancos_api, 'tem_vinculo', lambda *args: True)
    with site(app) as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel='chromium', executable_path=os.getenv('BROWSER_EXECUTABLE'))
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        login_ui(page, url)
        page.get_by_role('button', name='Sem squad', exact=True).click()
        page.wait_for_selector('#gridBody a')
        page.goto(url + '/analise.html')
        page.get_by_role('button', name='Geral', exact=True).click()
        page.locator('[data-squad-choice="Sem squad"]').click()
        page.wait_for_selector('tr[data-client]')
        row = page.locator('tr[data-client]').first
        assert row.get_attribute('onmouseover') is None
        row.dispatch_event('mouseover')
        assert page.evaluate('window.__auditXss') is None
        assert row.get_attribute('data-client') == payload
        page.set_viewport_size({'width': 390, 'height': 844})
        overflow = page.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,20).map(e=>({tag:e.tagName,id:e.id,cls:e.className,width:e.getBoundingClientRect().width}))")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), overflow
        page.screenshot(path=str(tmp_path / 'analise-mobile.png'), full_page=True)
        page.goto(url + '/index.html')
        page.get_by_role('button', name='Extrair campanhas', exact=True).click()
        expect(page.locator('#jobHistory')).to_contain_text('campanhas', timeout=15000)
        page.goto(url + '/equipe.html')
        page.wait_for_selector('#users tr')
        assert page.locator('#users').inner_text().find('admin@example.test') >= 0
        assert not errors
        browser.close()
