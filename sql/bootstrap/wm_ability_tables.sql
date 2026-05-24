-- WM Ability Effect Tracking
-- Every durable effect is bound to an aura_spell_id applied to the target.
-- No aura present on target = no effect runs. Aura removal = effect ends.

CREATE TABLE IF NOT EXISTS wm_active_effect (
    id              INT UNSIGNED        NOT NULL AUTO_INCREMENT,
    effect_key      VARCHAR(200)        NOT NULL,
    target_kind     ENUM('player','creature') NOT NULL,
    target_guid     INT UNSIGNED        NOT NULL,
    source_player_guid INT UNSIGNED     NOT NULL,
    ability_key     VARCHAR(120)        NOT NULL,
    aura_spell_id   INT UNSIGNED        NOT NULL,
    effect_kind     VARCHAR(80)         NOT NULL,
    effect_params_json TEXT             DEFAULT NULL,
    state           ENUM('active','ended','expired','dispelled') NOT NULL DEFAULT 'active',
    applied_at      DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      DATETIME            DEFAULT NULL,
    ended_at        DATETIME            DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_effect_key (effect_key),
    INDEX idx_target_active     (target_kind, target_guid, state),
    INDEX idx_aura_active        (aura_spell_id, state),
    INDEX idx_expires            (expires_at, state),
    INDEX idx_source             (source_player_guid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
