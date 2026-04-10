import random

mid_price = 100.0
position = 0
cash = 0.0
avg_entry_price = 0.0


def update_average_entry_price(old_position, old_avg, trade_size, trade_price, new_position):
    """
    Update average entry price when adding to a position.
    This simple version only recalculates properly when position direction stays the same.
    """
    if new_position == 0:
        return 0.0

    # If opening new position from flat
    if old_position == 0:
        return trade_price

    # If increasing same-side position
    if (old_position > 0 and trade_size > 0) or (old_position < 0 and trade_size < 0):
        total_value = (old_avg * abs(old_position)) + (trade_price * abs(trade_size))
        return total_value / abs(new_position)

    # If reducing position, keep old average unless flipped
    if abs(trade_size) < abs(old_position):
        return old_avg

    # If flipped direction, new average becomes trade price
    return trade_price


def calculate_unrealised_pnl(position, mid_price, avg_entry_price):
    if position > 0:
        return position * (mid_price - avg_entry_price)
    elif position < 0:
        return abs(position) * (avg_entry_price - mid_price)
    return 0.0


def market_news():
    """
    Random chance of news moving the market.
    """
    global mid_price

    news_events = [
        ("Strong economic data", 1.5),
        ("Central bank hints at rate cuts", -1.2),
        ("Geopolitical tensions rise", -2.0),
        ("Major company reports strong earnings", 1.0),
        ("Quiet market", 0.0),
    ]

    event, move = random.choice(news_events)
    mid_price += move
    return event, move


def client_decision(mid_price, bid, offer):
    """
    Very basic AI client:
    - sometimes buys if offer looks okay
    - sometimes sells if bid looks okay
    - otherwise does nothing
    """
    action_roll = random.random()

    # Client has their own idea of fair value
    fair_value = mid_price + random.uniform(-1.0, 1.0)

    if action_roll < 0.33:
        # Client may buy from you
        if offer <= fair_value:
            return "buy"
    elif action_roll < 0.66:
        # Client may sell to you
        if bid >= fair_value:
            return "sell"

    return "pass"


print("Welcome to the Trading Game.")
print("You are a market maker.")
print("Quote a bid and offer each round.\n")

for round_number in range(1, 11):
    print(f"\n--- Round {round_number} ---")

    event, move = market_news()
    print(f"News: {event} ({move:+.2f})")
    print(f"Current mid price: {mid_price:.2f}")

    # User inputs bid and offer
    try:
        bid = float(input("Enter your bid price: "))
        offer = float(input("Enter your offer price: "))
    except ValueError:
        print("Invalid input. Round skipped.")
        continue

    if bid >= offer:
        print("Invalid quote: bid must be less than offer.")
        continue

    old_position = position
    old_avg = avg_entry_price

    decision = client_decision(mid_price, bid, offer)

    if decision == "buy":
        print(f"Client buys from you at {offer:.2f}")
        # You sell 1 unit
        position -= 1
        cash += offer
        avg_entry_price = update_average_entry_price(
            old_position, old_avg, -1, offer, position
        )

    elif decision == "sell":
        print(f"Client sells to you at {bid:.2f}")
        # You buy 1 unit
        position += 1
        cash -= bid
        avg_entry_price = update_average_entry_price(
            old_position, old_avg, 1, bid, position
        )

    else:
        print("No trade this round.")

    unrealised = calculate_unrealised_pnl(position, mid_price, avg_entry_price)
    total_pnl = cash + (position * mid_price)

    print(f"Position: {position}")
    print(f"Cash: {cash:.2f}")
    print(f"Average entry price: {avg_entry_price:.2f}")
    print(f"Unrealised PnL: {unrealised:.2f}")
    print(f"Total PnL (simple mark-to-market): {total_pnl:.2f}")

print("\nGame over.")