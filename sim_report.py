#!/usr/bin/env python3
"""Run simulation and produce detailed report."""
import config_loader
config_loader.check_and_reload()
from game_engine import GameState
import re, sys

W, H, P, T = 35, 28, 5, 150
if len(sys.argv) > 1: T = int(sys.argv[1])

print("Running %dx%d, %d players, %d turns..." % (W, H, P, T))
log = GameState.simulate(width=W, height=H, num_players=P, num_turns=T)
r = log['result']

print("=" * 70)
print("Winner: %s (%s) at turn %s" % (r['winner'], r.get('victory_type', '?'), r['final_turn']))
print("Cities: %s, Roads: %s, Improvements: %s" % (r['total_cities'], r['total_roads'], r['total_improvements']))
print("=" * 70)

for s in r['scores']:
    alive = '' if s['alive'] else ' [DEAD]'
    ratio = s['units'] / max(1, s['cities']) if s['cities'] > 0 else 0
    flag = ' !!!' if ratio > 6 else ''
    print("  %s (%s): score=%s, %su/%sc=%.1f/city, gold=%s, culture=%s, techs=%s%s%s" %
          (s['name'], s['civ'], s['score'], s['units'], s['cities'], ratio,
           s['gold'], s['culture_pool'], s['techs'], alive, flag))
    if s.get('city_names'):
        print("    Cities: %s" % ', '.join(s['city_names']))

# Count events
ev = {}
bld = {}
uprod = {}
for t in log['turns']:
    for e in t['events']:
        if not isinstance(e, str): continue
        for tag, key in [('SETTLE:', 'settle'), ('destroyed', 'combat'), ('grew to', 'growth'),
                         ('gang-up', 'gangup'), ('ALLIANCE WAR', 'alliance_war'),
                         ('DIPLO: WAR', 'direct_war'), ('DIPLO: peace', 'peace'),
                         ('ALLIANCE with', 'alliance_form'), ('AUTO-DISBAND', 'auto_disband'),
                         ('TIMEOUT', 'settler_timeout')]:
            if tag in e: ev[key] = ev.get(key, 0) + 1
        if 'Disbanded' in e and 'bankrupt' in e: ev['disband_bankrupt'] = ev.get('disband_bankrupt', 0) + 1
        if 'captured' in e.lower(): ev['capture'] = ev.get('capture', 0) + 1
        if 'eliminated' in e.lower(): ev['eliminated'] = ev.get('eliminated', 0) + 1
        m = re.search(r'built (\w+)$', e)
        if m: bld[m.group(1)] = bld.get(m.group(1), 0) + 1
        m = re.search(r'produced (\w+)$', e)
        if m: uprod[m.group(1)] = uprod.get(m.group(1), 0) + 1

print("\n--- EVENTS ---")
for k, v in sorted(ev.items(), key=lambda x: -x[1]):
    print("  %s: %s" % (k, v))

print("\n--- BUILDINGS (top 15) ---")
for b, c in sorted(bld.items(), key=lambda x: -x[1])[:15]:
    print("  %s: %s" % (b, c))

print("\n--- UNITS PRODUCED ---")
for u, c in sorted(uprod.items(), key=lambda x: -x[1]):
    print("  %s: %s" % (u, c))

# Settler wander
wanders = []
for t in log['turns']:
    for e in t['events']:
        if isinstance(e, str) and 'wandered=' in e:
            wt = int(e.split('wandered=')[1].split('t')[0])
            wanders.append(wt)
            if wt > 8: print("  LONG wander: T%s %st" % (t['turn'], wt))
if wanders:
    print("\n--- SETTLERS: avg=%.1ft, max=%st, count=%s ---" % (sum(wanders)/len(wanders), max(wanders), len(wanders)))

# City health last turn
print("\n--- CITY HEALTH (last turn) ---")
for t in log['turns'][-1:]:
    for e in t['events']:
        if isinstance(e, dict) and 'cities' in e:
            for c in e['cities']:
                nb = len(c['buildings']) if isinstance(c['buildings'], list) else c['buildings']
                conn = c.get('connected_to_capital', '?')
                print("  %s: %s pop=%s bld=%s connected=%s" %
                      (e['player'], c['name'], c['pop'], nb, conn))

# Diplomacy timeline
print("\n--- DIPLOMACY (first 12) ---")
dc = 0
for t in log['turns']:
    for e in t['events']:
        if isinstance(e, str) and ('DIPLO' in e or 'ALLIANCE' in e) and dc < 12:
            print("  T%s: %s" % (t['turn'], e[:90]))
            dc += 1

# Production AI
print("\n--- PRODUCTION AI (last 6) ---")
prods = []
for t in log['turns']:
    for e in t['events']:
        if isinstance(e, str) and 'PROD-SCORE' in e:
            prods.append("T%s: %s" % (t['turn'], e[:100]))
for p in prods[-6:]:
    print("  %s" % p)

# Verdict
print("\n" + "=" * 70)
print("VERDICT:")
problems = []
max_ratio = max((s['units']/max(1, s['cities']) for s in r['scores'] if s['cities'] > 0), default=0)
if max_ratio > 6: problems.append("Military spam: %.1f/city" % max_ratio)
if ev.get('gangup', 0) > 20: problems.append("Too many gang-ups: %s" % ev['gangup'])
long_w = sum(1 for w in wanders if w > 10)
if long_w: problems.append("%s settlers wandered >10 turns" % long_w)
if ev.get('disband_bankrupt', 0) > 15: problems.append("Mass bankruptcy: %s disbands" % ev['disband_bankrupt'])
if not problems:
    print("  No major issues! Game is balanced.")
else:
    for p in problems:
        print("  PROBLEM: %s" % p)
ratios = []
for s in r['scores']:
    if s['alive'] and s['cities'] > 0:
        ratios.append("%s:%s/%s" % (s['name'][:12], s['units'], s['cities']))
print("  Alive ratios: %s" % ' | '.join(ratios))
