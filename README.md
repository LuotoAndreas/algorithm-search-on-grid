# Ruudukkopohjainen reitinhakusimulaatio

Tämä ohjelma visualisoi ja vertailee reitinhakualgoritmeja ruudukkoympäristössä. Ohjelmassa voi valita lähtöpisteen, maalin, esteitä ja algoritmin sekä seurata, miten reitti lasketaan ja miten ajonaikaiset esteet vaikuttavat uudelleenreititykseen.

## Käynnistä venv virtuaaliympäristö 

```bash
start.bat
```

## Asennus

Asenna riippuvuudet projektikansiossa:

```bash
pip install -r requirements.txt
```

## Asetukset
config.py tiedostossa voi säätää ruudukon kokoa

## Ohjelman käynnistys

Käynnistä visualisointiohjelma:

```bash
python main.py
```


## Käyttöjärjestys

1. Valitse lähtöpiste painikkeella **Lähtöpiste** ja klikkaa ruudukkoa.
2. Valitse maali painikkeella **Maali** ja klikkaa ruudukkoa.
3. Lisää esteitä joko piirtämällä hiirellä tai painikkeella **Satunnaisesteet**.
4. Valitse algoritmi: **Dijkstra**, **A*** tai **D* Lite**.
5. Laske reitti painikkeella **Laske reitti**.
6. Aloita ajosimulaatio painikkeella **Aloita ajo**.

## Esteiden käyttö

- Vasen hiiren painike lisää esteitä.
- Oikea hiiren painike poistaa esteitä.
- Ajon aikana reitin eteen voi lisätä uuden esteen klikkaamalla ruudukkoa.
- **Dynaamiset +** ja **Dynaamiset -** muuttavat automaattisten ajonaikaisten esteiden määrää.

## Tulokset

Käyttöliittymässä yksittäisen ajon tulokset tallennetaan tiedostoon:

```text
results.csv
```

Laajemmat koetulokset voi luoda komennolla:

```bash
python run_experiments.py --scenarios 50 --dynamic-obstacles 7 --obstacle-probability 0.15
```
Jossa 50 on ajettavien skenaarioiden määrä, dynamic-obstacles puolestaan monenko esteen kanssa ajoja ajetaan. (nyt valittuna 7 esteen kanssa. Valita voi myös vaikka --dynamic-obstacles 7,10 jolloin ajetaan 7 ja sitten 10 esteen kanssa per ajo.) Probability on generoitujen esteiden tiheys ruudukolla.

Komentoriviltä ajon tulokset tallentuvat tiedostoon:

```text
experiment_results.csv
```

Tuloksia voi tiivistää komennolla:

```bash
python summarize_results.py
```

## Tärkeimmät tiedostot

- `main.py` – interaktiivinen visualisointiohjelma
- `algorithms.py` – Dijkstra ja A*
- `dstar_lite.py` – D* Lite -toteutus
- `grid.py` – ruudukon ja esteiden hallinta
- `metrics.py` – mittareiden keruu ja tallennus
- `run_experiments.py` – automaattiset kokeet
- `summarize_results.py` – tulosten yhteenveto

## Huomio

Ohjelma käyttää yksinkertaistettua ruudukkoympäristöä.