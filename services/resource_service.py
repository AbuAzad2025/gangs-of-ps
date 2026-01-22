from extensions import db
from models.user import User
from models.log import UserLog
from models.system import SystemConfig
from flask import request, flash, current_app
from flask_babel import _
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
import json
from datetime import datetime, timezone
from utils.resource_audit import allow_resource_mutation, disallow_resource_mutation


class ResourceService:
    @staticmethod
    def modify_resources(
            user_id,
            changes,
            reason,
            check_balance=True,
            auto_commit=True,
            expected_version=None,
            set_fields=None,
            log_extra=None):
        """
        Atomically modifies user resources and logs the transaction.

        Args:
            user_id (int): The ID of the user.
            changes (dict): Dictionary of changes, e.g., {'money': -100, 'gold': 50}.
            reason (str): Reason for the transaction.
            check_balance (bool): If True, ensures sufficient funds.
            auto_commit (bool): If True, commits immediately.
            expected_version (int, optional): If provided, ensures the user's version matches this value.
                                              Useful for optimistic locking when the changes depend on previous state.
            set_fields (dict, optional): Dictionary of fields to set directly (e.g., {'hospital_until': datetime...}).
        """
        token = allow_resource_mutation()
        try:
            # 1. Fetch current state
            user = db.session.query(User).filter_by(
                id=user_id).populate_existing().with_for_update().first()
            if not user:
                return False

            # Optimistic Locking Check
            if expected_version is not None and user.version != expected_version:
                got_version = user.version
                current_app.logger.warning(
                    f"Transaction Failed: Version Mismatch (Expected {expected_version}, Got {got_version})")
                return False

            # Daily Money Limit Check
            if 'money' in changes and changes['money'] > 0:
                # Whitelist of reasons that ARE subject to the cap (Earnings)
                # "Except if bought with real money" implies everything else is capped.
                # However, to avoid capping P2P transfers and destroying
                # economy, we only cap Faucets.
                CAPPED_REASONS = [
                    'crime_reward', 'crime_success', 'work_salary', 'search_streets_found',
                    'daily_task_reward', 'race_prize_win', 'mugging_win',
                    'heist_reward', 'organized_crime_reward', 'daily_reward'
                    # REMOVED: 'smuggling_sell', 'sell_smuggling' - because they involve capital (Revenue vs Profit).
                    # REMOVED: 'casino_...' - because it involves betting stake.
                ]
                # Removing casino reasons from the list above effectively exempts them.
                # Only "Faucet" earnings are capped.

                if reason in CAPPED_REASONS:
                    try:
                        today = datetime.now(timezone.utc).date()
                        # Reset if new day
                        if user.daily_money_date != today:
                            user.daily_money_earned = 0
                            user.daily_money_date = today

                        limit = int(
                            SystemConfig.get_value(
                                'economy_daily_money_limit',
                                '1000000'))
                        current_daily = user.daily_money_earned or 0

                        if current_daily >= limit:
                            changes['money'] = 0  # Cap reached
                            try:
                                flash(
                                    _(
                                        'لقد وصلت للحد اليومي للكسب (%(limit)s$)! لن تكسب المزيد اليوم.',
                                        limit=limit,
                                    ),
                                    'warning')
                            except BaseException:
                                pass
                        elif current_daily + changes['money'] > limit:
                            allowed = limit - current_daily
                            changes['money'] = allowed
                            user.daily_money_earned += allowed
                            try:
                                flash(
                                    _(
                                        'لقد وصلت للحد اليومي للكسب! تم إضافة %(allowed)s$ فقط.',
                                        allowed=allowed,
                                    ),
                                    'warning')
                            except BaseException:
                                pass
                        else:
                            user.daily_money_earned += changes['money']
                    except Exception as e:
                        current_app.logger.error(
                            f"Error in daily limit check: {e}")

            before_state = {}
            for res, amount in changes.items():
                if hasattr(user, res):
                    before_state[res] = getattr(user, res)
                else:
                    raise ValueError(f"Invalid resource: {res}")

            if set_fields:
                for field, value in set_fields.items():
                    if hasattr(user, field):
                        before_state[field] = getattr(user, field)
                    else:
                        raise ValueError(f"Invalid field: {field}")

            # 2. Validation
            if check_balance:
                for res, amount in changes.items():
                    if res == 'heat':
                        continue  # Heat is special, handled by add_heat clamping
                    if amount < 0:
                        current_val = getattr(user, res)
                        if current_val + amount < 0:
                            current_app.logger.warning(
                                "Transaction Failed: Insufficient funds for %s (Current: %s, Change: %s)",
                                res,
                                current_val,
                                amount,
                            )
                            return False  # Insufficient funds

            # 3. Apply Changes
            # Since we used with_for_update(), we can safely modify the object.

            for res, amount in changes.items():
                if res == 'heat':
                    user.add_heat(amount)
                else:
                    current_val = getattr(user, res)
                    setattr(user, res, current_val + amount)

            if set_fields:
                for field, value in set_fields.items():
                    setattr(user, field, value)

            # 4. Prepare After State
            after_state = {}
            for res in changes.keys():
                after_state[res] = getattr(user, res)

            if set_fields:
                for field in set_fields.keys():
                    after_state[field] = getattr(user, field)

            # 5. Log Transaction
            ip = request.remote_addr if request else '127.0.0.1'
            ua = request.user_agent.string if request else 'System'

            def _make_serializable(d):
                new_d = {}
                for k, v in d.items():
                    if isinstance(
                            v, (datetime, float, int, str, bool, type(None))):
                        if isinstance(v, datetime):
                            new_d[k] = v.isoformat()
                        else:
                            new_d[k] = v
                    elif hasattr(v, 'isoformat'):  # Date objects
                        new_d[k] = v.isoformat()
                    else:
                        new_d[k] = str(v)
                return new_d

            details_payload = dict(changes)
            if isinstance(log_extra, dict):
                for k, v in log_extra.items():
                    if k not in details_payload:
                        details_payload[k] = v

            log = UserLog(
                user_id=user_id,
                action=reason.upper(),
                details=json.dumps(_make_serializable(details_payload)),
                result='success',
                before_state=_make_serializable(before_state),
                after_state=_make_serializable(after_state),
                ip_address=ip,
                user_agent=ua
            )
            db.session.add(log)

            # 6. Commit
            if auto_commit:
                db.session.commit()
            else:
                db.session.flush()  # Ensure changes are pending in session

            return True

        except StaleDataError:
            db.session.rollback()
            # Optimistic locking failure - data changed concurrently
            current_app.logger.warning(
                "Transaction Failed: StaleDataError (Concurrent Modification)")
            return False

        except SQLAlchemyError as e:
            db.session.rollback()
            # Log error internally if needed
            current_app.logger.error(f"Transaction Failed: {e}")
            return False
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Transaction Error: {e}")
            return False
        finally:
            try:
                disallow_resource_mutation(token)
            except Exception:
                pass
