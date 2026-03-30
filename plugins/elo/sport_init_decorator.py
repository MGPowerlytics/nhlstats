"""
Decorator for sport Elo classes to eliminate duplicate __init__ code.

XP Principle: Once and Only Once (DRY) - Provides a reusable way to add
sport-specific __init__ methods without duplicating code across multiple
sport Elo classes.
"""

from typing import Callable, Type, Any


def sport_elo_init(
    default_k_factor: float = 20.0,
    default_home_advantage: float = 100.0,
    default_initial_rating: float = 1500.0,
    sport_name: str = "Sport",
) -> Callable[[Type], Type]:
    """
    Class decorator to add sport-specific __init__ method to Elo classes.

    This eliminates duplicate __init__ code across CBA, MLB, NBA, and
    Unrivaled Elo classes while maintaining backward compatibility.

    Args:
        default_k_factor: Sport-specific default K-factor
        default_home_advantage: Sport-specific default home advantage
        default_initial_rating: Sport-specific default initial rating
        sport_name: Name of the sport for documentation

    Returns:
        Class decorator function
    """

    def decorator(cls: Type) -> Type:
        """
        Actual decorator that adds the __init__ method to the class.
        """
        # Store the defaults as class attributes for reference
        cls.DEFAULT_K_FACTOR = default_k_factor
        cls.DEFAULT_HOME_ADVANTAGE = default_home_advantage
        cls.DEFAULT_INITIAL_RATING = default_initial_rating
        cls.SPORT_NAME = sport_name

        # Get the original __init__ if it exists (from parent class)
        original_init = getattr(cls, "__init__", None)

        def new_init(
            self,
            k_factor: float = default_k_factor,
            home_advantage: float = default_home_advantage,
            initial_rating: float = default_initial_rating,
            **kwargs: Any,
        ) -> None:
            # Call parent class __init__ with the parameters
            if original_init:
                original_init(
                    self,
                    k_factor=k_factor,
                    home_advantage=home_advantage,
                    initial_rating=initial_rating,
                    **kwargs,
                )

        # Create the docstring with formatted values
        docstring = f"""
            Initialize {sport_name} Elo rating system.

            Args:
                k_factor: K-factor for rating updates (default {default_k_factor})
                home_advantage: Home advantage in Elo points (default {default_home_advantage})
                initial_rating: Initial rating for new teams (default {default_initial_rating})
                **kwargs: Additional arguments passed to parent __init__
            """
        new_init.__doc__ = docstring.strip()

        # Replace the class's __init__ method
        cls.__init__ = new_init

        return cls

    return decorator
