# Green tests. Stranded robot.

This checkout of brean/python-pathfinding has a demo-only integration in
/app/src/pathfinding/rescue.py. The delivery planner passes a static route
smoke test but dispatches robots into closures after the map changes.

Repair plan_route(matrix, start, goal, blocked=()) so consecutive calls within
one process always return a minimum-cost legal cardinal route for the CURRENT
request, endpoints included, or [] if no route exists. Positive matrix values
are entry costs and 0 is a wall. blocked contains temporary (x,y) closures.
A previously closed bridge can reopen; terrain costs can change; dimensions
can change. Do not mutate inputs or expose mutable cached routes to callers.
Use the existing pathfinding library. Edit only source, not tests.

This is a deliberately faulty demo integration, NOT a reported upstream bug.
The simulation and verification are supplied only after your repair.
