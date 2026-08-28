"""Passages for people to read aloud while recording a reference clip.

A cloned voice is only as good as its reference. Reading prepared text beats
improvising: it keeps the speaker fluent, fills the clip with connected speech
instead of hesitation, and covers a wide spread of sounds. These passages are
written for that job - roughly fifteen to twenty seconds each, mixing plosives,
fricatives, nasals and diphthongs, with statements and questions so the model
hears more than one intonation pattern.
"""

from dataclasses import dataclass

# Average read-aloud pace, used to estimate how long a passage takes.
WORDS_PER_MINUTE = 150


@dataclass(frozen=True)
class Passage:
    title: str
    text: str

    @property
    def words(self) -> int:
        return len(self.text.split())

    @property
    def approx_seconds(self) -> int:
        return round(self.words / WORDS_PER_MINUTE * 60)


PASSAGES: tuple[Passage, ...] = (
    Passage(
        "The Harbour",
        "The old harbour wakes just before six, when the fishing boats push out "
        "through a thin grey mist. Gulls argue above the pier, and somewhere a "
        "bell buoy keeps slow time. By noon the fog burns off, the water turns a "
        "sharp blue, and the whole town smells of salt and diesel.",
    ),
    Passage(
        "Unexpected Guest",
        "Did you really walk all the way here in this rain? You should have "
        "called - I would have picked you up. Hang your jacket by the radiator "
        "and I will put the kettle on. There is fresh bread on the counter, "
        "though I warn you, I burned the bottom of it rather badly.",
    ),
    Passage(
        "The Workshop",
        "My grandfather kept every tool he ever owned, hung in careful rows above "
        "his bench: chisels, calipers, a heavy brass plane worn smooth at the "
        "grip. He could judge a joint by sound alone. Measure twice, he would "
        "say, then measure once again, because wood forgives nothing and "
        "remembers everything.",
    ),
    Passage(
        "Night Train",
        "The train left at half past eleven, nearly empty, rocking gently through "
        "fields I could not see. A woman two rows ahead was reading by phone "
        "light. Outside, small towns arrived and vanished - a petrol station, a "
        "bridge, six orange windows - and then nothing but dark glass and my own "
        "reflection.",
    ),
    Passage(
        "Slow Cooking",
        "Warm the oil, then add the onions and let them soften slowly; do not "
        "rush this part. Stir in the garlic, the paprika, and a generous pinch of "
        "salt. Once it smells sweet rather than sharp, pour in the tomatoes, "
        "lower the heat, and leave it alone for about forty minutes.",
    ),
)


def passage_at(index: int) -> Passage:
    """Passage at `index`, wrapping around so callers can just keep counting."""
    return PASSAGES[index % len(PASSAGES)]
