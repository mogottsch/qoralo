#!/usr/bin/env python3
"""Optional local-file Chromium playback check, not a listening verdict.

Requires playwright==1.56.0 in a separate QA environment. CHROMIUM_EXECUTABLE
can select an existing compatible Chromium; otherwise Playwright's default.
"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', type=Path, help='Optional NEW JSON report; default prints only')
args = parser.parse_args()
if args.report and args.report.exists():
    raise FileExistsError(args.report)

with sync_playwright() as p:
    executable = os.environ.get('CHROMIUM_EXECUTABLE')
    browser = p.chromium.launch(headless=True, executable_path=executable, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto((ROOT / 'index.html').as_uri(), wait_until='load')
    assert page.locator('audio').count() == 6
    page.wait_for_function('Array.from(document.querySelectorAll("audio")).every(a => a.readyState >= 1 && Number.isFinite(a.duration) && a.duration > 0)')
    players = []
    for index in range(6):
        audio = page.locator('audio').nth(index)
        # Clicking a real player establishes browser user activation first.
        audio.click()
        audio.evaluate('(a) => a.play()')
        page.wait_for_function('(i) => document.querySelectorAll("audio")[i].currentTime > 0.1', arg=index)
        state = audio.evaluate('(a) => ({src:a.getAttribute("src"), duration:a.duration, currentTime:a.currentTime, paused:a.paused, error:a.error?.code || null})')
        assert not state['paused'] and state['error'] is None
        audio.evaluate('(a) => a.pause()')
        players.append(state)
    assert not errors
    overflow = page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth')
    assert not overflow, '390px horizontal overflow'
    (ROOT / '.local').mkdir(exist_ok=True)
    page.screenshot(path=str(ROOT / '.local/comparison-mobile.png'), full_page=True)
    page.set_viewport_size({'width': 1280, 'height': 900})
    page.screenshot(path=str(ROOT / '.local/comparison-desktop.png'), full_page=True)
    report = {'status': 'passed_browser_decode_and_playback_not_human_listening',
              'playwright': importlib.metadata.version('playwright'), 'chromium': browser.version,
              'origin': 'local file:// comparison, not a public deployment', 'players': players,
              'page_errors': errors, 'mobile_width': 390, 'horizontal_overflow': overflow}
    print(json.dumps(report, indent=2))
    if args.report:
        with args.report.open('x') as stream:
            stream.write(json.dumps(report, indent=2) + '\n')
    browser.close()
