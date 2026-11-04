from worlds.LauncherComponents import Component, Type, components, launch as launch_component

from .world import KotOR2World as KotOR2World


def launch_client(*args: str) -> None:
    from .client import launch
    launch_component(launch, name="KotOR2Client", args=args)


components.append(Component("KOTOR 2 Client", func=launch_client, component_type=Type.CLIENT,
                            game_name="Star Wars Knights of the Old Republic II", supports_uri=True,
                            description="Connects Knights of the Old Republic II (K2APBridge) to a multiworld."))
