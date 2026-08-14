"""Seed the facts feature with ten topics and twenty facts each.

Usage::

    ./run djangomanage seedfacts

Creates the ten topics (cars, science, animals, geography, history, space,
food, sports, music, technology) and twenty facts each — 200 rows total — via
``save_with_logs`` so each created row is audit-logged. Idempotent: re-running
clears the existing facts and topics first (``--keep`` skips the clear); that
clear is a bulk queryset delete, so it leaves no ``deleted`` audit trail.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils.text import slugify

from djangoapp.models import User
from ourapp.models import Fact, Topic

# Seed data: topic name -> 20 facts (the slug is derived from the name via
# slugify). Ten topics × twenty facts = 200 rows.
FACTS: dict[str, list[str]] = {
    "cars": [
        "The first car was built in 1886 by Karl Benz.",
        "The Toyota Corolla is the best-selling car model of all time.",
        "Electric cars predate gasoline cars by several decades.",
        "The windshield wiper was invented by Mary Anderson in 1903.",
        "The fastest production car can exceed 300 miles per hour.",
        "Most cars contain about 30,000 individual parts.",
        "The first speed limit for cars was 4 mph in the United Kingdom.",
        "The Volkswagen Beetle was produced for over 65 years.",
        "The first three-point seatbelt was introduced by Volvo in 1959.",
        "The average car is parked about 95 percent of the time.",
        "The first car radio was offered by Motorola in 1930.",
        "The Ford Model T was the first mass-produced car.",
        "A modern Formula 1 car can corner at over 5 g of force.",
        "The Bugatti Veyron has ten radiators to cool its engine.",
        "The first traffic light was installed in 1868 in London.",
        "Antilock brakes were first used on airplanes before cars.",
        "The Tesla Roadster was the first highway-capable electric sports car.",
        "The first odometer was used on carriages before cars existed.",
        "The average car tire rotates about 42 million times in its life.",
        "The Lamborghini company started by building tractors.",
    ],
    "science": [
        "Water expands when it freezes, unlike most substances.",
        "A bolt of lightning is roughly five times hotter than the Sun's surface.",
        "The human body contains about 37 trillion cells.",
        "Sound travels about four times faster in water than in air.",
        "A teaspoon of neutron star material would weigh a billion tons.",
        "Honey never spoils; jars thousands of years old are still edible.",
        "Octopus blood is blue because it uses copper, not iron.",
        "A day on Venus is longer than its year.",
        "DNA in your body could stretch to the Sun and back many times.",
        "Bananas are slightly radioactive due to their potassium.",
        "Light from the Sun takes about eight minutes to reach Earth.",
        "The Earth's inner core is as hot as the Sun's surface.",
        "Sharks predate trees by millions of years.",
        "A rainbow is a full circle, usually seen as an arc from the ground.",
        "Glass is technically a very slow-moving liquid.",
        "The average cloud weighs around a million pounds.",
        "Helium can defy gravity and crawl up walls.",
        "Most of the universe's mass is dark matter we cannot see.",
        "Hot water can freeze faster than cold water under some conditions.",
        "A single bolt of lightning contains enough energy to toast bread.",
    ],
    "animals": [
        "A group of flamingos is called a flamboyance.",
        "Honeybees can recognize human faces.",
        "Octopuses have three hearts and blue blood.",
        "A snail can sleep for up to three years.",
        "Wombat droppings are cube-shaped.",
        "Dolphins give each other names using signature whistles.",
        "A blue whale's heart can weigh as much as a car.",
        "Cows have best friends and get stressed when separated.",
        "Elephants are the only mammals that cannot jump.",
        "A sloth takes two weeks to digest a single meal.",
        "Polar bears have black skin under their white fur.",
        "Crows can use tools and remember human faces for years.",
        "A housefly hums in the key of F.",
        "Sea otters hold hands while sleeping to avoid drifting apart.",
        "The mantis shrimp can punch with the speed of a bullet.",
        "Frogs absorb water through their skin rather than drinking.",
        "A hummingbird weighs less than a penny.",
        "Gorillas can catch human colds and illnesses.",
        "The heart of a hummingbird beats over 1,000 times per minute.",
        "Kangaroos cannot walk backwards.",
    ],
    "geography": [
        "Russia spans eleven time zones, more than any other country.",
        "Canada has more lakes than the rest of the world combined.",
        "The Pacific Ocean is larger than all land on Earth combined.",
        "Mount Everest grows about four millimeters taller each year.",
        "Africa is the only continent in all four hemispheres.",
        "Iceland has no mosquitoes, despite a wet climate.",
        "The Sahara is the largest hot desert, but Antarctica is the largest overall.",
        "There is a town in Norway called Hell that freezes over each winter.",
        "The Amazon Rainforest produces about 20 percent of the world's oxygen.",
        "Greenland is the world's largest island that is not a continent.",
        "The Dead Sea is shrinking by about one meter each year.",
        "Papua New Guinea has over 800 living languages.",
        "The Nile and the Amazon are the two longest rivers, by most measures.",
        "Monaco is smaller than New York's Central Park.",
        "The Great Wall of China is not visible from the Moon.",
        "About 90 percent of the Earth's freshwater is in Antarctica.",
        "Indonesia is made up of over 17,000 islands.",
        "The Mariana Trench is deeper than Mount Everest is tall.",
        "Liechtenstein is one of only two doubly landlocked countries.",
        "The Danube flows through ten different countries.",
    ],
    "history": [
        "Cleopatra lived closer in time to the Moon landing than to the pyramids' construction.",
        "The University of Oxford is older than the Aztec Empire.",
        "The shortest war in history lasted about 38 minutes.",
        "The Eiffel Tower was originally meant to be temporary.",
        "The first recorded recipe was for beer, in ancient Sumer.",
        "The Great Wall took over 2,000 years to build in stages.",
        "Albert Einstein was offered the presidency of Israel in 1952.",
        "The ancient Romans used crushed mouse brains as toothpaste.",
        "Napoleon was once attacked by a horde of rabbits.",
        "The printing press was invented by Gutenberg around 1440.",
        "The first Olympic Games were held in 776 BC in Greece.",
        "Julius Caesar was kidnapped by pirates as a young man.",
        "The Titanic sank the same year that chewing gum was patented.",
        "The Berlin Wall fell in 1989 after 28 years.",
        "The oldest known written story is the Epic of Gilgamesh.",
        "Susan B. Anthony was fined for voting illegally in 1872.",
        "The first computer programmer was Ada Lovelace in the 1800s.",
        "The Statue of Liberty was a gift from France in 1886.",
        "The Magna Carta was signed in 1215 by King John.",
        "The Cold War lasted over four decades without direct major conflict.",
    ],
    "space": [
        "There are more stars in the universe than grains of sand on Earth.",
        "A day on Mercury lasts about 59 Earth days.",
        "Neutron stars can spin 600 times per second.",
        "Space is completely silent because there is no medium for sound.",
        "The footprints on the Moon will likely last millions of years.",
        "Jupiter's Great Red Spot is a storm larger than Earth.",
        "Saturn could float in water because it is mostly gas.",
        "A year on Pluto takes 248 Earth years.",
        "The Sun makes up 99.8 percent of the solar system's mass.",
        "There may be a planet made largely of diamond.",
        "Light from the Sun takes eight minutes to reach Earth.",
        "The largest known star would take 1,000 years to circle.",
        "Venus rotates backwards compared to most planets.",
        "The Moon is slowly drifting away from Earth.",
        "A spoonful of a neutron star would weigh a billion tons.",
        "Mars has the tallest volcano in the solar system.",
        "The first artificial satellite was Sputnik, launched in 1957.",
        "Black holes can spin at nearly the speed of light.",
        "There are more volcanoes on Jupiter's moon Io than on Earth.",
        "The universe is estimated to be about 13.8 billion years old.",
    ],
    "food": [
        "Honey is the only food that does not spoil.",
        "Peanuts are legumes, not nuts.",
        "The most stolen food worldwide is cheese.",
        "A strawberry is not technically a berry, but a banana is.",
        "Tomatoes were once thought to be poisonous in Europe.",
        "The world's most expensive spice is saffron.",
        "Apples float because they are one-quarter air.",
        "The first chocolate chip cookie was invented in 1938.",
        "Carrots were originally purple, not orange.",
        "The average person eats about 35 tons of food in a lifetime.",
        "Potatoes were the first vegetable grown in space.",
        "The popsicle was invented by an 11-year-old in 1905.",
        "Vanilla comes from a type of orchid.",
        "Ketchup was sold as medicine in the 1830s.",
        "The world's hottest chili is the Carolina Reaper.",
        "Cheese is the most stolen food on Earth.",
        "The croissant was invented in Austria, not France.",
        "An ear of corn always has an even number of rows.",
        "The sandwich was named after the Earl of Sandwich.",
        "Coffee was discovered by a goat herder in Ethiopia.",
    ],
    "sports": [
        "The Olympic Games have been held every four years since 1896.",
        "A golf ball has 336 dimples on average.",
        "The marathon distance of 26.2 miles was fixed in 1921.",
        "The first World Cup was held in Uruguay in 1930.",
        "Boxing became a legal sport in 1901 in some countries.",
        "The fastest tennis serve ever recorded is over 160 mph.",
        "Basketball was invented in 1891 by James Naismith.",
        "The Tour de France has run since 1903.",
        "Wimbledon is the oldest tennis tournament in the world.",
        "The first modern Olympics had only 14 nations.",
        "A hockey puck can travel over 100 mph.",
        "The Super Bowl is among the most-watched broadcasts each year.",
        "Table tennis was originally called gossima and whiff-whaff.",
        "The first Boston Marathon was held in 1897.",
        "Volleyball was invented in 1895, just before basketball spread.",
        "The first soccer rules were written in 1863 in England.",
        "Formula 1 cars can corner at over 5 g of force.",
        "The heaviest sumo wrestler weighed over 500 pounds.",
        "A baseball game has no fixed time limit.",
        "Cricket matches can last up to five days.",
    ],
    "music": [
        "The oldest known musical instrument is a 40,000-year-old flute.",
        "The Beatles hold the record for most number-one hits in the US.",
        "A grand piano has over 12,000 parts.",
        "The shortest song ever recorded lasts under two seconds.",
        "Listening to music can lower your heart rate and stress.",
        "The term 'rock and roll' was coined in the 1950s.",
        "The violin evolved from older bowed instruments in Italy.",
        "Mozart composed his first symphony at age eight.",
        "The longest concert ever lasted over 600 hours.",
        "The first music video aired on MTV was 'Video Killed the Radio Star.'",
        "A standard orchestra has around 75 to 100 musicians.",
        "The ukulele originated in Hawaii, based on Portuguese instruments.",
        "Beethoven continued composing after losing his hearing.",
        "The most expensive musical instrument sold was a Stradivarius violin.",
        "Singing in a choir can boost your immune system.",
        "The guitar has roots in instruments over 4,000 years old.",
        "The world's largest instrument is a pipe organ in a cave.",
        "Vinyl records were the dominant format before cassettes and CDs.",
        "The harmonica is the best-selling instrument in the world.",
        "Music can trigger the release of dopamine in the brain.",
    ],
    "technology": [
        "The first computer bug was an actual moth found in 1947.",
        "More people on Earth have mobile phones than working toilets.",
        "The first webcam watched a coffee pot at Cambridge University.",
        "About 90 percent of the world's data was created in the last few years.",
        "The QWERTY keyboard layout was designed to slow typists down.",
        "The first 1-gigabyte hard drive cost about 40,000 dollars.",
        "There are over 700 known programming languages.",
        "The average smartphone has more computing power than Apollo 11.",
        "The first message sent over the internet was 'LO.'",
        "About 70 percent of all software bugs are never noticed by users.",
        "The first domain name registered was symbolics.com in 1985.",
        "Email predates the internet as we know it.",
        "The original name for Bluetooth was a Viking king.",
        "Wi-Fi does not stand for anything officially.",
        "The first iPhone was released in 2007.",
        "Linux was created by Linus Torvalds in 1991.",
        "The '@' symbol was chosen for email in 1971.",
        "Robots have replaced many assembly-line jobs since the 1960s.",
        "The CAPTCHA was invented to tell humans and bots apart.",
        "Cloud computing stores data on remote servers, not your device.",
    ],
}


class Command(BaseCommand):
    """Seed the facts database (ten topics, twenty facts each)."""

    help = "Seed the facts feature with ten topics and twenty facts each."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--keep",
            action="store_true",
            help="Keep existing facts/topics instead of clearing first.",
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401 # Django passes **options as untyped command flags
        keep: bool = options["keep"]
        # A sentinel system user records the seed as the audit actor so seeded
        # rows carry a created_by (BaseModel.created_by is RESTRICT-null, so a
        # None actor is fine too, but a real actor reads better in the UI).
        seeder = self._seeder()

        with transaction.atomic():
            if not keep:
                Fact.objects.all().delete()
                Topic.objects.all().delete()
            topics = self._seed_topics(seeder)
            fact_count = self._seed_facts(topics, seeder)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(topics)} topics and {fact_count} facts."
            )
        )

    def _seeder(self) -> User | None:
        """The actor recorded on seeded rows (an existing superuser, else None)."""
        return User.objects.filter(is_superuser=True).order_by("id").first()

    def _seed_topics(self, seeder: User | None) -> dict[str, Topic]:
        """Create one topic per name (alphabetical), keyed by slug.

        Reuses an existing topic by slug under ``--keep`` (the slug is unique),
        so re-seeding appends fresh facts without duplicating topics. A new
        topic is created **unsaved** and persisted via ``save_with_logs`` so the
        CREATE branch runs — stamping ``created_by`` and writing a ``created``
        log row. (``get_or_create`` would persist first, forcing the no-op
        UPDATE branch, which skips ``created_by`` and writes no log.)
        """
        topics: dict[str, Topic] = {}
        for name in sorted(FACTS):
            slug = slugify(name)
            try:
                topic = Topic.objects.get(slug=slug)
            except Topic.DoesNotExist:
                topic = Topic(name=name, slug=slug)
                topic.save_with_logs(actor=seeder)
            topics[slug] = topic
        return topics

    def _seed_facts(self, topics: dict[str, Topic], seeder: User | None) -> int:
        """Create every fact under its topic; return the count written."""
        count = 0
        for slug, topic in topics.items():
            for text in FACTS[topic.name]:
                fact = Fact(text=text, topic=topic)
                fact.save_with_logs(actor=seeder)
                count += 1
        return count
