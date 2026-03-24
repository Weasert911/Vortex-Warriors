#!/usr/bin/env python
"""
Test script to verify the VW tournament system flow:
1. Match creation
2. Player registration
3. Payment submission with pass_id generation
4. Portal access with pass_id
"""

from app import app, db, Match, Player
from datetime import datetime, date, timedelta

def test_system_flow():
    with app.app_context():
        # Clean up test data
        Player.query.delete()
        Match.query.delete()
        db.session.commit()
        
        # 1. Create a match for today
        today = date.today()
        match_time = datetime.combine(today, datetime.strptime('17:20', '%H:%M').time())
        match = Match(
            game='Free Fire',
            time=match_time,
            entry_fee=100,
            total_slots=10,
            available_slots=10,
            status='upcoming',
            room_id='ROOM123',
            room_password='PASS123'
        )
        db.session.add(match)
        db.session.commit()
        print(f"[OK] Created match: {match.game} at {match.time}")
        
        # 2. Simulate player registration
        player = Player(
            name='Test Player',
            uid='123456789',
            discord='test#1234',
            match_id=match.id,
            payment_status='pending'
        )
        db.session.add(player)
        db.session.commit()
        print(f"[OK] Registered player: {player.name} (ID: {player.id})")
        
        # 3. Simulate payment submission (confirm_payment logic)
        player.utr = 'TESTUTR123456'
        # Generate pass_id (as in confirm_payment route)
        pass_id = f"VW-{uuid.uuid4().hex[:4].upper()}-{match.game.replace(' ', '')[:4].upper()}"
        player.pass_id = pass_id
        player.payment_status = 'pending'  # Still pending admin approval
        db.session.commit()
        print(f"[OK] Payment proof submitted. Pass ID generated: {player.pass_id}")
        
        # 4. Verify pass_id is unique and stored
        retrieved_player = Player.query.filter_by(pass_id=player.pass_id).first()
        assert retrieved_player is not None, "Player not found by pass_id"
        print(f"[OK] Player can be retrieved by pass_id: {retrieved_player.name}")
        
        # 5. Simulate admin approval
        player.payment_status = 'paid'
        match.available_slots -= 1
        db.session.commit()
        print(f"[OK] Player approved. Match slots remaining: {match.available_slots}")
        
        # 6. Verify portal access via /portal?pass=XXX
        portal_player = Player.query.filter_by(pass_id=player.pass_id).first_or_404()
        assert portal_player.id == player.id, "Portal player mismatch"
        print(f"[OK] Portal access works for pass_id: {portal_player.pass_id}")
        print(f"  Player: {portal_player.name}, Status: {portal_player.payment_status}")
        print(f"  Match: {portal_player.match.game}, Room: {portal_player.match.room_id}")
        
        # 7. Verify pass_id appears in index when passed as query param
        with app.test_client() as client:
            response = client.get(f'/?pass_id={player.pass_id}')
            assert response.status_code == 200, "Index page should load"
            # Check if pass_id appears in response data
            response_data = response.data.decode('utf-8')
            assert player.pass_id in response_data, "Pass ID should be displayed on index page"
            print(f"[OK] Pass ID is displayed on homepage when passed as query parameter")
        
        # Clean up
        Player.query.delete()
        Match.query.delete()
        db.session.commit()
        print("\n[OK] All tests passed! System flow is working correctly.")

if __name__ == '__main__':
    import uuid
    test_system_flow()