"""The tunable content surface — declarative data only, no logic. Everything that
decides *what a report says* lives here: area-type profiles, seasonal clothing and
frequency, and the hostile / protester behaviour repertoires. Extend by editing
these tables; the generation logic stays untouched."""

CARS = ["Volvo V70", "VW Golf", "Toyota Corolla", "Audi A4", "Skoda Octavia",
        "Ford Focus", "Kia Ceed", "Tesla Model 3", "Volvo XC60", "Renault Clio",
        "Hyundai i30", "Dacia Duster", "Peugeot 308", "Nissan Qashqai"]
DOGS = ["en hund", "två hundar", "en labrador", "en liten terrier", "en schäfer"]
COLOURS = ["ljus", "gul", "röd", "blå", "grön", "orange", "grå", "beige"]

# --- Area types -------------------------------------------------------------
# reports_per_day: base civilian volume; places: name templates; civil: benign
# activity prose ({car}/{dog}/{colour} filled in); vehicles: civilians often
# carry a plate here.
AREAS = {
    "urban": {
        "reports_per_day": 45,
        "vehicles": True,
        "places": ["Stora torget", "Centralstationen", "Köpcentret", "Busshållplatsen",
                   "Parkeringshuset", "Stadsparken", "Gågatan", "Rådhusplatsen",
                   "Tunnelbaneuppgången", "Kvarteret vid kyrkan", "Hamngatan", "Skolgården"],
        "civil": ["Fotgängare passerade på gågatan.", "{car} körde förbi i trafiken.",
                  "Familj handlade i köpcentret.", "Hundrastare med {dog} i stadsparken.",
                  "Bussresenärer väntade vid hållplatsen.", "Cyklist i {colour} jacka passerade.",
                  "Leveransbil lossade utanför butiken.", "Ungdomar samlades på torget.",
                  "{car} parkerade i parkeringshuset.", "Pensionär matade duvor i parken.",
                  "Servicepersonal utanför kontoret.", "Gatumusikant vid stationen."],
    },
    "suburban": {
        "reports_per_day": 20,
        "vehicles": True,
        "places": ["Villagatan", "Radhusområdet", "Lekplatsen", "Närköpet",
                   "Idrottsplatsen", "Busshållplats Björkvägen", "Återvinningen",
                   "Skogsdungen", "Parkeringen vid skolan", "Gång- och cykelvägen"],
        "civil": ["Barnfamilj på lekplatsen.", "{car} lämnade barn vid skolan.",
                  "Hundrastare med {dog} på gångvägen.", "Joggare i {colour} passerade.",
                  "Granne klippte häcken.", "Paketbud levererade i villaområdet.",
                  "Ungdomar spelade boll på idrottsplatsen.", "{car} tvättades på uppfarten.",
                  "Pensionärer promenerade längs villagatan.", "Återvinning lämnades vid stationen."],
    },
    "rural": {
        "reports_per_day": 7,
        "vehicles": True,
        "places": ["Byvägen", "Åkerkanten", "Skogsbrynet", "Ladugården", "Grusvägen",
                   "Sjöboden", "Korsningen vid kyrkan", "Betesmarken", "Traktorvägen",
                   "Milstolpen", "Gårdsinfarten"],
        "civil": ["Lantbruksfordon på åkern, sedvanligt arbete.", "Traktor plöjde fältet.",
                  "{car} körde förbi på grusvägen.", "Hundrastare med {dog} längs byvägen.",
                  "Bonde kontrollerade stängsel.", "Bär- eller svampplockare i skogsbrynet.",
                  "Postbil levererade till gården.", "Ryttare passerade på traktorvägen.",
                  "Pensionärspar promenerade längs vägen.", "Fiskare vid sjöboden."],
    },
    "airport": {
        "reports_per_day": 22,
        "vehicles": True,
        "places": ["Norra banänden", "Hangarområdet", "Klubbstugan", "Infarten till fältet",
                   "Grusparkeringen", "Skogsbrynet väster om banan", "Södra banänden",
                   "Vägkorsningen mot samhället", "Åkerkanten öster om banan", "Motionsspåret"],
        "civil": ["Segelflygare riggade vid hangaren.", "Familj tittade på flygplan från parkeringen.",
                  "{car} parkerade vid klubbstugan.", "Traktor klippte gräs längs banan.",
                  "Motionär joggade längs vägen.", "Hundrastare med {dog} på grusvägen.",
                  "Paketbil levererade till klubbstugan.", "Cyklist i {colour} jacka vid grinden.",
                  "Fältarbetare kontrollerade markeringar.", "Barn matade fåglar vid parkeringen."],
    },
    "port": {
        "reports_per_day": 28,
        "vehicles": True,
        "places": ["Kajen", "Containerterminalen", "Färjeläget", "Lastkajen", "Fisketorget",
                   "Vågbrytaren", "Hamnkontoret", "Uppställningsplatsen", "Bränslekajen",
                   "Gästhamnen", "Bommen vid infarten"],
        "civil": ["Lastbil hämtade container vid terminalen.", "Färjepassagerare gick i land.",
                  "{car} väntade vid färjeläget.", "Fiskare landade fångst vid kajen.",
                  "Hamnarbetare lastade på kajen.", "Fritidsbåt lade till i gästhamnen.",
                  "Hundrastare med {dog} längs vågbrytaren.", "Turister fotograferade båtarna.",
                  "Bränsleleverans vid bränslekajen.", "Servicebil vid hamnkontoret."],
    },
    "military": {
        "reports_per_day": 16,
        "vehicles": True,
        "places": ["Vakten", "Norra grinden", "Övningsfältet", "Förrådsområdet",
                   "Staketet mot skogen", "Parkeringen utanför", "Bommen", "Skjutbanan",
                   "Vägen mot kasernen", "Uppställningsytan"],
        "civil": ["Personal passerade vakten.", "{car} lämnades på besöksparkeringen.",
                  "Leverans anmäldes vid grinden.", "Motionär joggade längs staketet utanför.",
                  "Hundrastare med {dog} på vägen utanför.", "Servicetekniker vid förrådet.",
                  "Buss släppte av personal vid bommen.", "Gräsklippning längs vägen.",
                  "Cyklist i {colour} passerade utanför staketet.", "Postbil vid vakten."],
    },
    "coastal": {
        "reports_per_day": 15,
        "vehicles": True,
        "places": ["Stranden", "Bryggan", "Klipporna", "Strandpromenaden", "Badplatsen",
                   "Fyren", "Kioskparkeringen", "Naturreservatet", "Piren", "Vikens infart"],
        "civil": ["Badgäster på stranden.", "Familj rastade vid bryggan.",
                  "{car} parkerade vid badplatsen.", "Hundrastare med {dog} på promenaden.",
                  "Fiskare vid piren, metspö och hink.", "Kajakpaddlare vid viken.",
                  "Solbadare vid klipporna.", "Glasskiosken hade kö.",
                  "Vandrare i {colour} i naturreservatet.", "Fritidsbåt ankrade i viken."],
    },
    "forest": {
        "reports_per_day": 5,
        "vehicles": False,
        "places": ["Skogsstigen", "Hygget", "Rastplatsen", "Timmervägen", "Myren",
                   "Fågeltornet", "Grillplatsen", "Vindskyddet", "Stenmuren", "Bäcken"],
        "civil": ["Vandrare med ryggsäck på stigen.", "Svampplockare i skogen.",
                  "Hundrastare med {dog} på timmervägen.", "Motionär sprang i spåret.",
                  "Fågelskådare vid tornet.", "Familj grillade vid rastplatsen.",
                  "Skogsarbetare vid hygget.", "Orienterare passerade myren.",
                  "Bärplockare längs bäcken.", "Cyklist i {colour} på skogsvägen."],
    },
}

# --- Seasons (by month) -----------------------------------------------------
# civ_mult scales civilian volume; upper/headwear/accessory feed the optional
# civilian appearance; day is the daytime hour band that biases benign timing.
SEASONS = {
    "vinter": {"months": [12, 1, 2], "civ_mult": 0.6, "day": (8, 16),
               "upper": ["täckjacka", "vinterjacka", "mörk parkas", "dunjacka"],
               "headwear": ["mössa", "pälsmössa", "luva"],
               "accessory": ["halsduk", "handskar", "ryggsäck"]},
    "vår": {"months": [3, 4, 5], "civ_mult": 0.9, "day": (6, 20),
            "upper": ["vårjacka", "regnjacka", "softshell", "collegetröja"],
            "headwear": ["keps", "mössa"],
            "accessory": ["ryggsäck", "axelväska", "paraply"]},
    "sommar": {"months": [6, 7, 8], "civ_mult": 1.2, "day": (5, 22),
               "upper": ["t-shirt", "linne", "tunn skjorta", "kortärmad tröja"],
               "headwear": ["keps", "solhatt", "bandana"],
               "accessory": ["solglasögon", "ryggsäck", "vattenflaska"]},
    "höst": {"months": [9, 10, 11], "civ_mult": 0.9, "day": (7, 18),
             "upper": ["höstjacka", "regnjacka", "yllekavaj", "windbreaker"],
             "headwear": ["keps", "mössa"],
             "accessory": ["paraply", "ryggsäck", "halsduk"]},
}

# --- Hostiles ---------------------------------------------------------------
# Distinct individuals detectable as a spatio-temporal/behavioural pattern near
# the AOI. `behaviour` prose carries the domain signature; `marks` are distinctive
# person descriptions (soft re-id). count default is random 2..10 per the spec.
HOSTILES = {
    "recon": {
        "night_bias": 0.6, "near_bias": 0.9, "appearances": (2, 4),
        "behaviour": [
            "Stod stilla länge och betraktade {obj}, fotograferade mot området.",
            "Långsam passage, andra varvet inom 25 minuter, iakttog in- och utfart.",
            "Antecknade i block medan fordon passerade infarten.",
            "Satt i parkerad bil med uppsikt mot {obj}, lämnade när patrull närmade sig.",
            "Mätte av sträckan längs staketet med stegräknare, undvek ögonkontakt.",
            "Riktade kikare mot {obj}, drog sig undan vid uppmärksamhet.",
            "Rörde sig längs skogsbrynet, verkade kartlägga kameraplaceringar.",
            "Stannade upprepat och tittade bakåt innan vidare mot {obj}."],
        "marks": ["mörk täckjacka, keps neddragen, solglasögon",
                  "ljusgrå softshell, axelremsväska, kort rakat hår",
                  "grön fältjacka, kikare runt halsen, skäggig",
                  "svart hoodie, ryggsäck med stativ, hörlurar",
                  "blå arbetsjacka, reflexväst men inget arbete utfört",
                  "beige rock, läderportfölj, prydligt klädd",
                  "mörk hoodie, kamera med teleobjektiv, ung",
                  "grå munkjacka, mörk mössa, anteckningsblock"],
    },
    "sabotage": {
        "night_bias": 0.85, "near_bias": 0.95, "appearances": (1, 3),
        "behaviour": [
            "Kände på grinden och testade låset vid {obj}.",
            "Rörde vid kabelskåp intill {obj}, drog sig undan när ljus tändes.",
            "Klättrade över stängslet mot {obj} och kröp längs diket.",
            "Bar verktygsväska, sysslade med något vid transformatorn.",
            "Placerade ett föremål invid {obj} och avlägsnade sig snabbt.",
            "Undersökte ventilations- och elskåp längs staketet.",
            "Forcerade en avspärrning och tog sig in mot {obj}.",
            "Manipulerade en bom och lämnade platsen till fots."],
        "marks": ["mörk overall, handskar, pannlampa",
                  "svart munkjacka, verktygsväska, mörk mössa",
                  "mörkblå arbetskläder, bultsax, ryggsäck",
                  "grå jacka, avbitartång, handskar",
                  "mörk täckjacka, kofot under armen",
                  "svarta kläder, ansiktsmask, liten ryggsäck"],
    },
    "infiltration": {
        "night_bias": 0.3, "near_bias": 0.8, "appearances": (2, 4),
        "behaviour": [
            "Försökte följa med personal in genom {obj}.",
            "Bar synbart passerkort men kändes inte igen av vakten.",
            "Skuggade en anställd mot {obj}, höll avstånd.",
            "Ställde ingående frågor om rutiner och passertider.",
            "Fotograferade skyltar och passersystem vid {obj}.",
            "Klädd som hantverkare, saknade arbetsorder, rörde sig fritt.",
            "Testade en dörr vid {obj} som skulle vara låst.",
            "Väntade vid personalingången och gled in vid vaktbyte."],
        "marks": ["mörk kavaj, portfölj, passerkort på snodd",
                  "hantverkarkläder, verktygsbälte, keps",
                  "vit skjorta, id-bricka, prydligt klädd",
                  "reflexväst, ritningsrulle, hjälm",
                  "beige rock, glasögon, axelväska",
                  "mörk pikétröja, headset, klippboard"],
    },
    "terrorism": {
        "night_bias": 0.35, "near_bias": 0.85, "appearances": (1, 3),
        "behaviour": [
            "Rekognoserade folksamlingen vid {obj}, räknade passager.",
            "Lämnade en oidentifierad väska nära {obj} och avlägsnade sig.",
            "Körde långsamt förbi {obj} upprepade gånger, filmade.",
            "Observerade vakters positioner och avlösningstider vid {obj}.",
            "Bar tung ryggsäck, verkade nervös, undvek kameror.",
            "Fotograferade in- och utfarter samt barriärer vid {obj}.",
            "Testade fordonsspärrar och avstånd till {obj}.",
            "Höll uppsikt över entrén och antecknade tider."],
        "marks": ["mörk jacka, tung ryggsäck, svettig och nervös",
                  "vid rock, handskar trots milt väder, mörk mössa",
                  "mörka kläder, oidentifierad väska, undvek ögonkontakt",
                  "keps neddragen, solglasögon, filmade med mobil",
                  "arbetsjacka, kartrulle, mätte avstånd",
                  "mörk huvtröja, ansiktet dolt, rörde sig snabbt"],
    },
}

# --- Challenging civilians (protesters) -------------------------------------
# Not hostile, but noisy: a GROUP gathers at one location on one day. size is the
# number of individual sightings the event produces.
PROTESTERS = {
    "demonstranter": {"size": (4, 12),
        "behaviour": ["Grupp med plakat samlades vid {obj}.",
                      "Demonstranter skanderade paroller mot {obj}.",
                      "Folksamling blockerade infarten till {obj}.",
                      "Talkör och banderoller vid {obj}.",
                      "Demonstrationståg passerade {obj}."],
        "marks": ["plakat och megafon", "banderoll, färgglada kläder",
                  "väst med slogan, flygblad", "flaggor och visselpipa"]},
    "miljöaktivister": {"size": (3, 10),
        "behaviour": ["Miljöaktivister kedjade fast sig vid {obj}.",
                      "Grupp satte upp banderoll mot utsläpp vid {obj}.",
                      "Aktivister blockerade transport vid {obj}.",
                      "Sittdemonstration på vägen mot {obj}.",
                      "Delade ut flygblad och krävde stopp vid {obj}."],
        "marks": ["gröna västar, banderoll", "målade ansikten, plakat",
                  "regnkläder, kedjor och lås", "flygblad och megafon"]},
    "fredsaktivister": {"size": (3, 9),
        "behaviour": ["Fredsaktivister höll tyst manifestation vid {obj}.",
                      "Grupp med fredsflaggor samlades utanför {obj}.",
                      "Ljusmanifestation mot militär närvaro vid {obj}.",
                      "Sång och plakat för nedrustning vid {obj}.",
                      "Vaka med ljus och banderoller vid {obj}."],
        "marks": ["fredsflagga, ljus", "vita band, plakat",
                  "regnbågsflagga, banderoll", "handmålade skyltar"]},
}
