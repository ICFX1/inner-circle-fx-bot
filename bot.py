import discord
from discord.ext import commands
import pandas as pd
import os
from dotenv import load_dotenv
from openai import OpenAI
import io
import base64
from datetime import datetime
import asyncio

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

client_ai = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

trade_journals = {}

BRIEFING_CHANNEL_ID = 1474414193838129338

async def post_daily_briefing():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.utcnow()
        # Post at 7:30am UK time (UTC+0 in winter, UTC+1 in summer)
        # Using 7:30 UTC to cover both
        if now.hour == 7 and now.minute == 30:
            channel = bot.get_channel(BRIEFING_CHANNEL_ID)
            if channel:
                try:
                    await channel.send("⏳ Generating today's market briefing...")

                    ai_response = client_ai.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {
                                "role": "system",
                                "content": """You are a professional forex analyst for The Inner Circle FX. 
                                Generate a concise daily market briefing formatted for Discord.
                                Include these sections:
                                
                                📅 DAILY OUTLOOK — Brief overview of today's market sentiment
                                
                                💱 PAIR BIAS
                                • GBPUSD — Bias + 1 sentence reason
                                • EURUSD — Bias + 1 sentence reason  
                                • USDJPY — Bias + 1 sentence reason
                                
                                🔑 KEY LEVELS TO WATCH — 2-3 important levels across the major pairs
                                
                                ⚠️ HIGH IMPACT NEWS — Any major news events today (if none, say clear calendar)
                                
                                💡 LONDON OPEN WATCH — What to look for in the 8-9am session
                                
                                Keep it concise and actionable. Format cleanly for Discord."""
                            },
                            {
                                "role": "user",
                                "content": f"Generate the daily forex market briefing for {now.strftime('%A %d %B %Y')}."
                            }
                        ]
                    )

                    briefing = ai_response.choices[0].message.content

                    embed = discord.Embed(
                        title=f"🌍 Daily Market Briefing — {now.strftime('%A %d %B %Y')}",
                        color=0xFFD700
                    )
                    embed.add_field(name="Today's Analysis", value=briefing[:1024], inline=False)
                    embed.set_footer(text="The Inner Circle FX | Where Serious Traders Come To Grow")

                    await channel.send(embed=embed)

                except Exception as e:
                    print(f"Error posting daily briefing: {e}")

            await asyncio.sleep(60)  # Wait 60 seconds after posting to avoid double post
        else:
            await asyncio.sleep(30)  # Check every 30 seconds


@bot.event
async def on_ready():
    print(f'{bot.user} is online and ready!')
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="the markets 📈"
    ))
    bot.loop.create_task(post_daily_briefing())


@bot.command(name='briefing')
async def manual_briefing(ctx):
    await ctx.send("⏳ Generating market briefing...")
    now = datetime.utcnow()
    try:
        ai_response = client_ai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """You are a professional forex analyst for The Inner Circle FX. 
                    Generate a concise daily market briefing formatted for Discord.
                    Include these sections:
                    
                    📅 DAILY OUTLOOK — Brief overview of today's market sentiment
                    
                    💱 PAIR BIAS
                    • GBPUSD — Bias + 1 sentence reason
                    • EURUSD — Bias + 1 sentence reason  
                    • USDJPY — Bias + 1 sentence reason
                    
                    🔑 KEY LEVELS TO WATCH — 2-3 important levels across the major pairs
                    
                    ⚠️ HIGH IMPACT NEWS — Any major news events today (if none, say clear calendar)
                    
                    💡 LONDON OPEN WATCH — What to look for in the 8-9am session
                    
                    Keep it concise and actionable. Format cleanly for Discord."""
                },
                {
                    "role": "user",
                    "content": f"Generate the daily forex market briefing for {now.strftime('%A %d %B %Y')}."
                }
            ]
        )

        briefing = ai_response.choices[0].message.content

        embed = discord.Embed(
            title=f"🌍 Daily Market Briefing — {now.strftime('%A %d %B %Y')}",
            color=0xFFD700
        )
        embed.add_field(name="Today's Analysis", value=briefing[:1024], inline=False)
        embed.set_footer(text="The Inner Circle FX | Where Serious Traders Come To Grow")

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error generating briefing: {str(e)}")


@bot.command(name='analyse')
async def analyse_trades(ctx):
    if not ctx.message.attachments:
        await ctx.send("📎 Please attach your MT4/MT5 trade history CSV file with this command.\n\nTo export: In MT4/MT5 go to Account History → Right click → Save as Report → Save as CSV")
        return

    await ctx.send("⏳ Analysing your trades... this may take a moment.")

    attachment = ctx.message.attachments[0]
    file_content = await attachment.read()

    try:
        df = pd.read_csv(io.StringIO(file_content.decode('utf-8')))
    except:
        try:
            df = pd.read_csv(io.StringIO(file_content.decode('latin-1')))
        except:
            await ctx.send("❌ Could not read your file. Please make sure it is saved as a CSV file from MT4/MT5.")
            return

    try:
        total_trades = len(df)

        profit_col = None
        for col in df.columns:
            if 'profit' in col.lower() or 'pnl' in col.lower():
                profit_col = col
                break

        if profit_col is None:
            await ctx.send("❌ Could not find profit column in your file. Please make sure you exported correctly from MT4/MT5.")
            return

        df[profit_col] = pd.to_numeric(df[profit_col], errors='coerce')
        winning_trades = len(df[df[profit_col] > 0])
        losing_trades = len(df[df[profit_col] < 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        total_profit = df[profit_col].sum()
        avg_win = df[df[profit_col] > 0][profit_col].mean() if winning_trades > 0 else 0
        avg_loss = df[df[profit_col] < 0][profit_col].mean() if losing_trades > 0 else 0

        symbol_col = None
        for col in df.columns:
            if 'symbol' in col.lower() or 'pair' in col.lower() or 'instrument' in col.lower():
                symbol_col = col
                break

        best_pair = "N/A"
        worst_pair = "N/A"
        if symbol_col:
            pair_performance = df.groupby(symbol_col)[profit_col].sum()
            best_pair = pair_performance.idxmax()
            worst_pair = pair_performance.idxmin()

        summary = f"""
        Total Trades: {total_trades}
        Win Rate: {win_rate:.1f}%
        Winning Trades: {winning_trades}
        Losing Trades: {losing_trades}
        Total Profit/Loss: {total_profit:.2f}
        Average Win: {avg_win:.2f}
        Average Loss: {avg_loss:.2f}
        Best Performing Pair: {best_pair}
        Worst Performing Pair: {worst_pair}
        """

        ai_response = client_ai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert forex trading coach for The Inner Circle FX community. 
                    Analyse the trader's statistics and provide specific, actionable feedback.
                    Be honest but encouraging. Focus on:
                    1. Their biggest strengths
                    2. Their biggest weaknesses
                    3. Specific areas to improve
                    4. A personalised weekly focus plan
                    Keep your response concise and formatted for Discord."""
                },
                {
                    "role": "user",
                    "content": f"Please analyse these trading statistics and provide coaching feedback:\n{summary}"
                }
            ]
        )

        ai_feedback = ai_response.choices[0].message.content

        embed = discord.Embed(
            title="🤖 Inner Circle FX — Trade Analysis",
            color=0xFFD700
        )
        embed.add_field(name="📊 Your Statistics", value=f"""
```
Total Trades:     {total_trades}
Win Rate:         {win_rate:.1f}%
Winning Trades:   {winning_trades}
Losing Trades:    {losing_trades}
Total P&L:        {total_profit:.2f}
Average Win:      {avg_win:.2f}
Average Loss:     {avg_loss:.2f}
Best Pair:        {best_pair}
Worst Pair:       {worst_pair}
```""", inline=False)
        embed.add_field(name="🧠 AI Coaching Feedback", value=ai_feedback[:1024], inline=False)
        embed.set_footer(text="The Inner Circle FX | Where Serious Traders Come To Grow")

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Something went wrong analysing your trades.\n\nError: {str(e)}")


@bot.command(name='journal')
async def journal_trade(ctx, *, trade_info):
    user_id = str(ctx.author.id)

    if user_id not in trade_journals:
        trade_journals[user_id] = []

    entry = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'trade': trade_info,
        'user': ctx.author.name
    }

    trade_journals[user_id].append(entry)

    embed = discord.Embed(
        title="📓 Trade Journal Entry Saved",
        color=0xFFD700
    )
    embed.add_field(name="Entry", value=trade_info, inline=False)
    embed.add_field(name="Date", value=entry['date'], inline=False)
    embed.add_field(name="Total Entries", value=str(len(trade_journals[user_id])), inline=False)
    embed.set_footer(text="The Inner Circle FX | Keep journaling — it's your edge")

    await ctx.send(embed=embed)


@bot.command(name='myjournal')
async def view_journal(ctx):
    user_id = str(ctx.author.id)

    if user_id not in trade_journals or len(trade_journals[user_id]) == 0:
        await ctx.send("📓 You haven't logged any trades yet. Use `/journal your trade details` to start journaling.")
        return

    entries = trade_journals[user_id][-5:]

    embed = discord.Embed(
        title=f"📓 {ctx.author.name}'s Trade Journal",
        color=0xFFD700
    )

    for i, entry in enumerate(entries, 1):
        embed.add_field(
            name=f"Entry {i} — {entry['date']}",
            value=entry['trade'][:200],
            inline=False
        )

    embed.set_footer(text=f"Showing last 5 entries | Total: {len(trade_journals[user_id])} | The Inner Circle FX")
    await ctx.send(embed=embed)


@bot.command(name='stats')
async def my_stats(ctx):
    embed = discord.Embed(
        title=f"📊 {ctx.author.name}'s Stats",
        color=0xFFD700
    )
    embed.add_field(
        name="How to get your full stats",
        value="Upload your MT4/MT5 CSV file using the `/analyse` command and the bot will give you a complete breakdown of your trading performance.",
        inline=False
    )
    embed.add_field(
        name="Journal Entries",
        value=str(len(trade_journals.get(str(ctx.author.id), []))),
        inline=False
    )
    embed.set_footer(text="The Inner Circle FX | Where Serious Traders Come To Grow")
    await ctx.send(embed=embed)


@bot.command(name='icfxhelp')
async def help_command(ctx):
    embed = discord.Embed(
        title="🤖 Inner Circle FX Bot — Commands",
        color=0xFFD700
    )
    embed.add_field(name="/analyse", value="Upload your MT4/MT5 CSV trade history and get a full AI powered analysis", inline=False)
    embed.add_field(name="/chart", value="Upload a TradingView screenshot and get AI analysis of bias, supply/demand zones and trade ideas", inline=False)
    embed.add_field(name="/briefing", value="Generate an instant market briefing for today", inline=False)
    embed.add_field(name="/journal [trade details]", value="Log a trade to your personal journal", inline=False)
    embed.add_field(name="/myjournal", value="View your last 5 journal entries", inline=False)
    embed.add_field(name="/stats", value="View your personal stats and journal count", inline=False)
    embed.set_footer(text="The Inner Circle FX | Where Serious Traders Come To Grow")
    await ctx.send(embed=embed)


@bot.command(name='chart')
async def analyse_chart(ctx):
    if not ctx.message.attachments:
        await ctx.send("📎 Please attach a TradingView screenshot with this command.")
        return

    await ctx.send("⏳ Analysing your chart... this may take 30 seconds.")

    attachment = ctx.message.attachments[0]
    print(f"Chart command received from {ctx.author.name}, attachment: {attachment.filename}")

    image_data = await attachment.read()
    encoded_image = base64.b64encode(image_data).decode('utf-8')

    try:
        ai_response = client_ai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert forex trader for The Inner Circle FX. Analyse the chart and respond with these sections:\n\n📈 OVERALL BIAS — State if bullish, bearish or neutral, then explain why in 2 sentences max (mention structure, key levels or momentum).\n🔴 SUPPLY ZONES — Key areas where price may reverse down with price levels.\n🟢 DEMAND ZONES — Key areas where price may reverse up with price levels.\n🎯 KEY LEVELS — Important support/resistance levels to watch.\n💡 TRADE IDEAS — Potential setups to watch for.\n\nBe specific with price levels. Keep the whole response concise."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}},
                        {"type": "text", "text": "Analyse this forex chart."}
                    ]
                }
            ],
            max_tokens=1000
        )

        analysis = ai_response.choices[0].message.content
        embed = discord.Embed(title="📊 Inner Circle FX — Chart Analysis", color=0xFFD700)
        embed.add_field(name="Analysis", value=analysis[:1024], inline=False)
        embed.set_footer(text="The Inner Circle FX | Where Serious Traders Come To Grow")
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error analysing chart: {str(e)}")


bot.run(DISCORD_TOKEN)
