#!/usr/bin/env bash
# Scaffold: a tiny Godot 4 game in GDScript — scenes, a player, combat math, a JSON save system and GUT
# tests. No web frontend, no server, no SQL, no LLM. Godot itself isn't installed, so its gates can't
# run here. Self-contained.
set -euo pipefail
git init -q
git config user.email eval@example.invalid
git config user.name eval
mkdir -p scenes scripts tests

cat > project.godot <<'EOF'
config_version=5

[application]
config/name="Tiny Dungeon"
run/main_scene="res://scenes/main.tscn"
EOF

cat > scenes/main.tscn <<'EOF'
[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/player.gd" id="1"]

[node name="Main" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]
script = ExtResource("1")
EOF

cat > scripts/player.gd <<'EOF'
extends CharacterBody2D

signal died

const SPEED := 120.0
var health := 10


func _physics_process(_delta: float) -> void:
	velocity = Input.get_vector("left", "right", "up", "down") * SPEED
	move_and_slide()


func take_damage(amount: int) -> void:
	health -= amount
	if health <= 0:
		died.emit()
EOF

cat > scripts/combat.gd <<'EOF'
class_name Combat


static func damage(attack: int, defense: int) -> int:
	return max(1, attack - defense)


static func roll_crit(rng: RandomNumberGenerator, chance: float) -> bool:
	return rng.randf() < chance
EOF

cat > scripts/save_game.gd <<'EOF'
extends Node

const SAVE_PATH := "user://save.json"


func save(data: Dictionary) -> void:
	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	file.store_string(JSON.stringify(data))


func load_game() -> Dictionary:
	if not FileAccess.file_exists(SAVE_PATH):
		return {}
	var text := FileAccess.get_file_as_string(SAVE_PATH)
	return JSON.parse_string(text)
EOF

cat > tests/test_combat.gd <<'EOF'
extends GutTest


func test_damage_never_below_one() -> void:
	assert_eq(Combat.damage(1, 5), 1)
EOF

cat > README.md <<'EOF'
# Tiny Dungeon
A small top-down dungeon game made with Godot 4.
Run the tests: `godot --headless -s addons/gut/gut_cmdln.gd -gdir=res://tests`
EOF

git add -A
git commit -q -m "tiny dungeon"
