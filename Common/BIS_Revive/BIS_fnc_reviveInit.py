/*
	Author: Thomas Ryan
	
	Description:
	Initialize the Revive system on all machines.
	
	Returns:
	True if successful, false if not.
*/

private ["_hasUnits", "_units", "_origin"];
_hasUnits = [_this, 0, false, [false]] call BIS_fnc_param;
_units = [_this, 1, [], [[]]] call BIS_fnc_param;
_origin = [_this, 2, -1, [objNull, -1]] call BIS_fnc_param;

// Track initialization of revive
if (isNil "BIS_revive_initialized") then {BIS_revive_initialized = false};

if (!(_hasUnits)) exitWith {
	if (isServer) then {
		// Create array to store units in need of revive
		if (isNil "BIS_revive_units") then {
			"First server init" call BIS_fnc_log;
			
			BIS_revive_units = [];
			publicVariable "BIS_revive_units";
			
			// Execute locally
			[true, BIS_revive_units] call BIS_fnc_reviveInit;
		};
		
		// Initialize revive for everyone forever
		if (isNil "BIS_revive_persistent") then {
			"Persistent call triggered" call BIS_fnc_log;
			
			BIS_revive_persistent = true;
			[[], "BIS_fnc_reviveInit", true, true] call BIS_fnc_MP;
		};
		
		// Send units to client
		if (typeName _origin == typeName objNull) then {
			["Sent to %1", _origin] call BIS_fnc_logFormat;
			[[true, BIS_revive_units], "BIS_fnc_reviveInit", _origin] call BIS_fnc_MP;
		};
	} else {
		if (isNil "BIS_revive_requestSent") then {
			"Request sent" call BIS_fnc_log;
			
			// Request init from server
			BIS_revive_requestSent = true;
			[[false, nil, player], "BIS_fnc_reviveInit", false] call BIS_fnc_MP;
		};
	};
};

if (BIS_revive_initialized) exitWith {true};

// Grab incapacitated units
BIS_revive_units = _units;

// Register that revive is enabled
[] call BIS_fnc_reviveEnabled;

// Handle local elements
{
	_x setVariable ["BIS_revive_incapacitated", true];
	_x switchMove "acts_InjuredLyingRifle02";
	[_x, 1] call BIS_fnc_reviveBleedOut;
	_x setCaptive true;
} forEach BIS_revive_units;

// Handle 3D icons
"INIT" call BIS_fnc_reviveIconControl;

// Dedicated servers need no longer apply
if (isDedicated) exitWith {true};

// Disable collisions with incapacitated units
{player disableCollisionWith _x; [[player, _x], "disableCollisionWith", _x] call BIS_fnc_MP} forEach BIS_revive_units;

// Establish local variables
BIS_revive_selected = objNull;			// Unit that the player is highlighting
BIS_revive_target = objNull;			// Unit that the player is trying to revive
BIS_revive_reviveDelayDefault = 6;		// Default time (in seconds) that it takes to revive a unit
BIS_revive_medikitMultiplier = 2;		// Multiplier acting on revive time if the player has a medikit
BIS_revive_reviveForceRespawnDelayDefault = 3;	// Default time (in seconds) that it takes to force respawn
BIS_revive_reviveBleedOutDelayDefault = 120;	// Default time (in seconds) that it takes to bleed out

// Establish object variables
player setVariable ["BIS_revive_incapacitated", false, true];	// Track whether the player is incapacitated
player setVariable ["BIS_revive_helper", objNull, true];	// Unit that is reviving the player
player setVariable ["BIS_revive_forceRespawn", false, true];	// Track whether player is forcing their respawn
player setVariable ["BIS_revive_dying", false, true];		// Track whether player is close to death

// Establish icon variables
BIS_revive_icons_icon = "a3\ui_f_mp_mark\data\revive\revive_ca.paa";
BIS_revive_icons_iconMedikit = "a3\ui_f_mp_mark\data\revive\revive_medikit_ca.paa";
BIS_revive_icons_selection = "Spine3";
BIS_revive_icons_visibleRange = 300;
BIS_revive_icons_size = 1.3;
BIS_revive_icons_alphaMin = 0.45;
BIS_revive_icons_alphaMax = 0.75;
BIS_revive_icons_text = toUpper (localize "STR_A3_Revive_Icon_text");
BIS_revive_icons_textRange = 25;
BIS_revive_icons_textTexture = [1,1,1,0] call BIS_fnc_colorRGBAtoTexture;
BIS_revive_icons_interactMin = 0.025;
BIS_revive_icons_interactMid = 0.1;
BIS_revive_icons_interactMax = 0.6;
BIS_revive_icons_distMin = 3.5;
BIS_revive_icons_distMid = 100;

// Precise detection of incapacitated units under the player's cursor
[] spawn {
	scriptName "BIS_fnc_reviveInit: cursorTarget";
	
	while {true} do {
		private ["_unit"];
		_unit = objNull;
		
		// Find unit under player's cursor
		waitUntil {
			if (count BIS_revive_units == 0) then {
				// No units are incapacitated
				sleep 0.05;
				true
			} else {
				private ["_sidePlayer"];
				_sidePlayer = player call BIS_fnc_objectSide;
				
				{
					sleep 0.05;
					
					private ["_dist"];
					_dist = (vehicle player) distance _x;
					
					if (
						_dist <= BIS_revive_icons_textRange
						&&
						{
							_x != player
							&&
							{
								private ["_sideTarget"];
								_sideTarget = _x call BIS_fnc_objectSide;
								_sidePlayer getFriend _sideTarget > 0
								&&
								{
									_sideTarget getFriend _sidePlayer > 0
									&&
									{
										private ["_pos"];
										_pos = worldToScreen (_x getVariable ["BIS_revive_iconPos", [10,10,10]]);
										
										if (count _pos == 0) then {
											// Unit isn't on screen
											false
										} else {
											_pos set [2,0];
											
											// Determine interaction size based on distance
											private ["_interact"];
											_interact = if (_dist <= BIS_revive_icons_distMin) then {
												// Player is really close
												BIS_revive_icons_interactMax
											} else {
												// Player is relatively close
												BIS_revive_icons_interactMid
											};
											
											// Unit must be in the center of the screen
											_pos distance [0.5,0.5,0] <= _interact
										};
									}
								}
							}
						}
					) exitWith {
						// Select unit
						_unit = _x;
					};
				} forEach BIS_revive_units;
				
				// Wait for unit to be selected
				!(isNull _unit)
			};
		};
		
		// Grab unit
		BIS_revive_selected = _unit;
		
		// Wait for the unit to be deselected
		waitUntil {
			sleep 0.05;
			
			if (!(_unit getVariable ["BIS_revive_incapacitated", false])) then {
				// Unit is no longer incapacitated
				true
			} else {
				private ["_dist"];
				_dist = (vehicle player) distance _unit;
				
				if (_dist > BIS_revive_icons_textRange) then {
					// Unit went out of range
					true
				} else {
					if (_unit == player) then {
						// Unit became the player
						true
					} else {
						private ["_sidePlayer", "_sideTarget"];
						_sidePlayer = player call BIS_fnc_objectSide;
						_sideTarget = _unit call BIS_fnc_objectSide;
						
						if (_sidePlayer getFriend _sideTarget == 0) then {
							// Player's side is enemy to the target
							true
						} else {
							if (_sideTarget getFriend _sidePlayer == 0) then {
								// Target's side is enemy to the player
								true
							} else {
								private ["_pos"];
								_pos = worldToScreen (_unit getVariable ["BIS_revive_iconPos", [10,10,10]]);
								
								if (count _pos == 0) then {
									// Unit isn't on screen
									true
								} else {
									_pos set [2,0];
									
									// Determine interaction size based on distance
									private ["_interact"];
									_interact = if (_dist <= BIS_revive_icons_distMin) then {
										// Player is really close
										BIS_revive_icons_interactMax
									} else {
										// Player is relatively close
										BIS_revive_icons_interactMid
									};
									
									// Unit left the center of the screen
									_pos distance [0.5, 0.5, 0] > _interact
								};
							};
						};
					};
				};
			};
		};
		
		// Clear selection
		BIS_revive_selected = objNull;
	};
};

// Start main revive control
[] call BIS_fnc_reviveControl;
"REVIVE" call BIS_fnc_reviveProgress;

// Register that revive was initialized
BIS_revive_initialized = true;

// Handle if client was killed to initialize revive or while it was initializing
if (!(alive player)) then {player call BIS_fnc_reviveOnPlayerKilled};

true