import os
from dotenv import load_dotenv
load_dotenv()

import time
import asyncio
import schedule
import threading
from bot_handler import BotHandler
from trade_analyzer import TradeAnalyzer
from matchup_optimizer import MatchupOptimizer
from espn_executor import ESPNExecutor

from waiver_scout import WaiverScout

bot = BotHandler()
trader = TradeAnalyzer()
optimizer = MatchupOptimizer()
scout = WaiverScout()

# Requires the espn cookies from the user environment if they want execution
executor = ESPNExecutor(
    league_id=int(os.environ.get("ESPN_LEAGUE_ID", 0)), 
    year=int(os.environ.get("ESPN_YEAR", 2026)), 
    espn_s2=os.environ.get("ESPN_S2", ""), 
    swid=os.environ.get("SWID", "")
)

def waiver_scout_job():
    print("Running Waiver Wire Scout...")
    try:
        moves = scout.scan_waivers()
    except Exception as e:
        print(f"Waiver Error: {e}")
        return
        
    for m in moves:
        add_p = m['add']
        drop_p = m['drop']
        msg = f"🚨 WAIVER ALERT 🚨\n\nAdd: {add_p['name']}\nDrop: {drop_p['name']}\n\nCommish says: {m['rationale']}"
        action_id = f"waiver_{add_p['id']}_{drop_p['id']}"
        
        async def on_approve(approved, a_id=add_p['id'], d_id=drop_p['id'], t_id=m['team_id'], current_week=m['current_week']):
            if approved:
                print(f"[ACTION] Claiming {add_p['name']} and dropping {drop_p['name']}")
                success, response_msg = executor.claim_waiver(team_id=t_id, add_player_id=a_id, drop_player_id=d_id, scoring_period=current_week)
                if success:
                    await bot.send_alert(f"✅ Waiver claim executed for {add_p['name']}!")
                else:
                    await bot.send_alert(f"❌ Waiver claim failed: {response_msg}")
            else:
                print(f"[ACTION] Waiver claim rejected.")
                
        asyncio.run(bot.send_approval_request(msg, action_id, on_approve))


def injury_cascade_job():
    print("Running Injury & Matchup Cascade...")
    try:
        warnings, recs, team_id = optimizer.analyze_start_sit()
    except Exception as e:
        if "403" in str(e) or "AccessDenied" in str(e) or "credentials" in str(e).lower():
            asyncio.run(bot.send_alert("⚠️ ACTION REQUIRED: Your ESPN Session has expired. Please reply with `/update_cookie <your_new_espn_s2_cookie>` to resume automation!"))
        else:
            print(f"Audit Error: {e}")
        return
    
    injury_found = False
    for w in warnings:
        asyncio.run(bot.send_alert(w))
        if "OUT" in w or "IR" in w or "SUSP" in w:
            injury_found = True
            
    if injury_found:
        print("Injury detected! Triggering emergency Waiver Scout...")
        waiver_scout_job()
        
    for r in recs:
        sit_p = r['sit']
        start_p = r['start']
        msg = f"🔄 Lineup Optimization: Sit {sit_p.name}, Start {start_p.name}\nReason: {r['reason']}"
        action_id = f"swap_{sit_p.playerId}_{start_p.playerId}"
        
        async def on_approve(approved, s1=sit_p, s2=start_p, t_id=team_id, current_week=optimizer.league.current_week):
            if approved:
                print(f"[ACTION] Swapping {s1.name} out for {s2.name}")
                
                # Map ESPN string slot to ID (WR=4, RB=2, TE=6, FLEX=23, QB=0, D/ST=16, K=17)
                slot_map = {"QB": 0, "RB": 2, "WR": 4, "TE": 6, "FLEX": 23, "D/ST": 16, "K": 17}
                from_slot = slot_map.get(s1.lineupSlot, 2)
                
                success, response_msg = executor.swap_lineup(
                    team_id=t_id, 
                    benched_player_id=s2.playerId, 
                    started_player_id=s1.playerId,
                    from_slot_id=from_slot,
                    scoring_period=current_week
                )
                if success:
                    await bot.send_alert(f"✅ Lineup swap executed for {s2.name}!")
                else:
                    await bot.send_alert(f"❌ Swap failed: {response_msg}")
            else:
                print("[ACTION] Lineup swap rejected.")
                
        asyncio.run(bot.send_approval_request(msg, action_id, on_approve))

def trade_scan_job():
    print("Scanning league for trade opportunities...")
    try:
        proposals = trader.scan_for_trades()
    except Exception as e:
        if "403" in str(e) or "AccessDenied" in str(e) or "credentials" in str(e).lower():
            asyncio.run(bot.send_alert("⚠️ ACTION REQUIRED: Your ESPN Session has expired. Please reply with `/update_cookie <your_new_espn_s2_cookie>` to resume automation!"))
        else:
            print(f"Trade Scan Error: {e}")
        return
    
    for p in proposals:
        give_names = ", ".join([x["name"] for x in p['give']])
        get_names = ", ".join([x["name"] for x in p['get']])
        give_ids = [x["id"] for x in p['give']]
        get_ids = [x["id"] for x in p['get']]
        
        msg = f"🤝 Trade Opportunity with {p['opponent']}!\n\nGive: {give_names}\nGet: {get_names}\n\nCommish says: {p['rationale']}"
        action_id = f"trade_{p['opponent_id']}"
        
        async def on_approve(approved, p_data=p, g_ids=give_ids, t_ids=get_ids):
            if approved:
                print(f"[ACTION] Proposing trade to {p_data['opponent']}")
                success, response_msg = executor.propose_trade(
                    from_team_id=p_data['my_team_id'], 
                    to_team_id=p_data['opponent_id'], 
                    give_player_ids=g_ids, 
                    get_player_ids=t_ids
                )
                if success:
                    await bot.send_alert(f"✅ Trade proposal sent to {p_data['opponent']}!")
                else:
                    await bot.send_alert(f"❌ Trade failed: {response_msg}")
            else:
                print(f"[ACTION] Trade with {p_data['opponent']} rejected.")
                
        asyncio.run(bot.send_approval_request(msg, action_id, on_approve))

def run_scheduler():
    # Matchup & Injury optimizations run 4x a day
    schedule.every().day.at("10:00").do(injury_cascade_job)
    schedule.every().day.at("14:00").do(injury_cascade_job)
    schedule.every().day.at("18:00").do(injury_cascade_job)
    schedule.every().day.at("21:00").do(injury_cascade_job)
    
    # Waiver scans run on Tuesdays before waivers clear
    schedule.every().tuesday.at("18:00").do(waiver_scout_job)
    
    # Trade scans run on Tuesdays (when waivers clear and people are panicking)
    schedule.every().tuesday.at("10:00").do(trade_scan_job)
    
    # Run once immediately on startup for testing
    injury_cascade_job()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    print("Starting Advanced Fantasy GM Agent Daemon...")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    bot.run_polling()
