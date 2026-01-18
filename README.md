VIŠEAGENTNA SIMULACIJA DINAMIKE POPULACIJA U EKOSUSTAVU GRABEŽLJIVAC - PLIJEN

Kratki sažetak aplikacije
Projekt implementira višeagentni simulacijski model u Pythonu koristeći SPADE framework, gdje svaki agent predstavlja pojedinačnu jedinku vrste plijena (Plijen) ili grabežljivca (Predator) koja se kreće kroz prostorno podijeljeno stanište (x, y koordinate), upravlja energijom, dobom, traži hranu (feed, hunt, search), razmnožava se (reproduce), odmara (rest) ili se kreće (move) te umire ovisno o lokalnim uvjetima. Simulacija je dinamična i stohastička, s promjenljivim vremenskim uvjetima (sunny, cloudy, rainy, storm) koji utječu na faktor regeneracije resursa (weatherfactor), vjerojatnost migracije (moveprob) i uspjeh predacije (predationsuccessprob). Cilj je analizirati utjecaj parametara poput brzine regeneracije resursa, intenziteta predacije i vremenskih uvjeta na stabilnost populacija, oscilacije broja živih jedinki i rizik izumiranja, vizualizirano kroz grafove energije i populacije iz CSV loga.


Na ovom repozitoriju priložena je dokumentacija koja je izrađena u svrhu kolegija Višeagentni sustavi na Fakultetu organizacije i informatike.
Dokumentacija sadrži glavnu python skriptu pod nazivom gui.py koja pokreće izrađen program.
Za pokretanje programa potrebno je u terminalu upisati python gui.py nakon čega se otvara skočni prozor s defaultno unesenim podacima koji se mogu i promijeniti.
Nakon toga prisne se tipka "Pokreni simulaciju" nakon čega se simulacija pokreće i kada se izvrši u prozoru Analiza vidljiva su prikazi dijagrama, ispis podataka i mogućnost uvoza prethodnih CSV datoteka za usporedbu rezultata.
Također, u repozitorij je stavljen PDF dokument VAS_projekt_Nina_Krsnik.pdf u kojem je tekstualno opisan projektni zadatak, a poveznica za pregled LaTex dokumenta u Overleafu:
https://www.overleaf.com/read/qmfxjrzkdhxq#81abf5
