from PIL import Image


class PlayerCard:
    cards = []  # Stores all cards on initialization

    def __init__(self, card_number, player_name, season_year, ability_rating, image_path):
        self.card_number = card_number
        self.player_name = player_name
        self.season_year = season_year
        self.ability_rating = ability_rating

        # Loads the image
        try:
            self.image = Image.open(image_path) # Resize the image
            self.image = self.image.resize((200, 300))
            print(f"Image loaded successfully: {image_path}")
        except Exception as e:
            print(f"Error loading image: {e}")
            self.image = None  # Set image to None if loading fails

        PlayerCard.cards.append(self) # Add this card to the list of created cards

    @classmethod
    def get_cards(cls): # return full list of cards
        return cls.cards


def initialize_player_cards(): # initializes list of cards
    lebron_13 = PlayerCard(
        card_number=1,
        player_name="LeBron James",
        season_year="2012-2013",
        ability_rating=99,
        image_path=r"C:\Users\brace\Downloads\cards\lebron13.png"
    )

    kd_14 = PlayerCard(
        card_number=2,
        player_name="Kevin Durant",
        season_year="2013-2014",
        ability_rating=94,
        image_path=r"C:\Users\brace\Downloads\cards\kd14.png"
    )

    curry_16 = PlayerCard(
        card_number=3,
        player_name="Stephen Curry",
        season_year="2015-2016",
        ability_rating=96,
        image_path=r"C:\Users\brace\Downloads\cards\curry16.png"
    )

    westbrook_17 = PlayerCard(
        card_number=4,
        player_name="Russell Westbrook",
        season_year="2016-2017",
        ability_rating=95,
        image_path=r"C:\Users\brace\Downloads\cards\westbrook17.png"
    )
    kobe_06 = PlayerCard(
        card_number=5,
        player_name="Kobe Bryant",
        season_year="2005-2006",
        ability_rating=97,
        image_path=r"C:\Users\brace\Downloads\cards\kobe06.png"
    )

    mj_96 = PlayerCard(
        card_number=6,
        player_name="Michael Jordan",
        season_year="1995-1996",
        ability_rating=98,
        image_path=r"C:\Users\brace\Downloads\cards\mj96.png"
    )

    shaq_01 = PlayerCard(
        card_number=7,
        player_name="Shaquille O'Neal",
        season_year="2000-2001",
        ability_rating=95,
        image_path=r"C:\Users\brace\Downloads\cards\shaq01.png"
    )

    duncan_03 = PlayerCard(
        card_number=8,
        player_name="Tim Duncan",
        season_year="2002-2003",
        ability_rating=97,
        image_path=r"C:\Users\brace\Downloads\cards\duncan03.png"
    )

    garnett_04 = PlayerCard(
        card_number=9,
        player_name="Kevin Garnett",
        season_year="2003-2004",
        ability_rating=94,
        image_path=r"C:\Users\brace\Downloads\cards\garnett04.png"
    )

    harden_18 = PlayerCard(
        card_number=10,
        player_name="James Harden",
        season_year="2017-2018",
        ability_rating=95,
        image_path=r"C:\Users\brace\Downloads\cards\harden18.png"
    )

    giannis_20 = PlayerCard(
        card_number=11,
        player_name="Giannis Antetokounmpo",
        season_year="2019-2020",
        ability_rating=96,
        image_path=r"C:\Users\brace\Downloads\cards\giannis20.png"
    )

    bird_86 = PlayerCard(
        card_number=12,
        player_name="Larry Bird",
        season_year="1985-1986",
        ability_rating=97,
        image_path=r"C:\Users\brace\Downloads\cards\bird86.png"
    )

    magic_87 = PlayerCard(
        card_number=13,
        player_name="Magic Johnson",
        season_year="1986-1987",
        ability_rating=96,
        image_path=r"C:\Users\brace\Downloads\cards\magic87.png"
    )

    dirk_11 = PlayerCard(
        card_number=15,
        player_name="Dirk Nowitzki",
        season_year="2010-2011",
        ability_rating=95,
        image_path=r"C:\Users\brace\Downloads\cards\dirk11.png"
    )

    ai_01 = PlayerCard(
        card_number=16,
        player_name="Allen Iverson",
        season_year="2000-2001",
        ability_rating=94,
        image_path=r"C:\Users\brace\Downloads\cards\ai01.png"
    )

    cp3_14 = PlayerCard(
        card_number=17,
        player_name="Chris Paul",
        season_year="2013-2014",
        ability_rating=95,
        image_path=r"C:\Users\brace\Downloads\cards\cp3_14.png"
    )

    kawhi_15 = PlayerCard(
        card_number=18,
        player_name="Kawhi Leonard",
        season_year="2014-2015",
        ability_rating=95,
        image_path=r"C:\Users\brace\Downloads\cards\kawhi15.png"
    )

    nash_06 = PlayerCard(
        card_number=19,
        player_name="Steve Nash",
        season_year="2005-2006",
        ability_rating=97,
        image_path=r"C:\Users\brace\Downloads\cards\nash06.png"
    )

    davis_20 = PlayerCard(
        card_number=21,
        player_name="Anthony Davis",
        season_year="2019-2020",
        ability_rating=95,
        image_path=r"C:\Users\brace\Downloads\cards\davis20.png"
    )

    embiid_22 = PlayerCard(
        card_number=22,
        player_name="Joel Embiid",
        season_year="2021-2022",
        ability_rating=94,
        image_path=r"C:\Users\brace\Downloads\cards\embiid22.png"
    )

    jokic_21 = PlayerCard(
        card_number=24,
        player_name="Nikola Jokić",
        season_year="2020-2021",
        ability_rating=97,
        image_path=r"C:\Users\brace\Downloads\cards\jokic21.png"
    )

# Ensure this code runs only when the script is executed directly
if __name__ == "__main__":
    initialize_player_cards()


