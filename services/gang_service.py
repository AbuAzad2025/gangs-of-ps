from extensions import db
from models.social import Gang
import json
from flask import current_app
from utils.essentials import load_json_seed


class GangService:
    _upgrades_data = None

    @classmethod
    def get_upgrades_data(cls):
        if cls._upgrades_data is None:
            try:
                cls._upgrades_data = load_json_seed('gang_upgrades.json')
            except Exception as e:
                current_app.logger.error(f"Error loading gang upgrades: {e}")
                cls._upgrades_data = []
        return cls._upgrades_data

    @classmethod
    def get_gang_buff(cls, gang_id, buff_type):
        """
        Returns the buff value for a specific buff type.
        buff_type: 'gym_rat', 'street_kings', 'bazaar_connections', 'security_detail'
        """
        if not gang_id:
            return 0

        gang = db.session.get(Gang, gang_id)
        if not gang or not gang.upgrades:
            return 0

        try:
            current_upgrades = json.loads(gang.upgrades)
        except BaseException:
            return 0

        level = current_upgrades.get(buff_type, 0)
        if level == 0:
            return 0

        upgrades_data = cls.get_upgrades_data()
        upgrade_def = next(
            (u for u in upgrades_data if u['id'] == buff_type), None)

        if not upgrade_def:
            return 0

        level_def = next(
            (level_row for level_row in upgrade_def['levels'] if level_row['level'] == level), None)
        if not level_def:
            return 0

        return level_def['effect']
