from app import app, db, Match, Player, Settings

with app.app_context():
    print('Matches:', Match.query.count())
    print('Players:', Player.query.count())
    print('Settings:', Settings.query.count())
    
    m = Match.query.first()
    if m:
        print('Match status:', m.status)
        print('Match time:', m.time)
        print('Match game:', m.game)
        print('Available slots:', m.available_slots)
    else:
        print('No matches found')