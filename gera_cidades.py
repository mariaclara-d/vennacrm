import json
cidades = sorted(set([
"Abadia de Goias/GO","Abadiania/GO","Acreuna/GO","Aguas Lindas de Goias/GO","Alexania/GO","Anapolis/GO","Aparecida de Goiania/GO","Aragarças/GO","Catalao/GO","Cristalina/GO","Formosa/GO","Goiania/GO","Goianesia/GO","Goias/GO","Inhumas/GO","Itumbiara/GO","Jatai/GO","Luziania/GO","Mineiros/GO","Morrinhos/GO","Niquelandia/GO","Pires do Rio/GO","Planaltina/GO","Porangatu/GO","Rio Verde/GO","Rubiataba/GO","Senador Canedo/GO","Trindade/GO","Uruacu/GO","Valparaiso de Goias/GO",
"Aracaju/SE","Estancia/SE","Itabaiana/SE","Lagarto/SE","Nossa Senhora do Socorro/SE","Sao Cristovao/SE",
"Belem/PA","Abaetetuba/PA","Altamira/PA","Ananindeua/PA","Braganca/PA","Castanhal/PA","Itaituba/PA","Maraba/PA","Paragominas/PA","Parauapebas/PA","Redencao/PA","Santarem/PA","Tucurui/PA",
"Belo Horizonte/MG","Alfenas/MG","Araguari/MG","Araxá/MG","Barbacena/MG","Betim/MG","Caete/MG","Conselheiro Lafaiete/MG","Contagem/MG","Coronel Fabriciano/MG","Curvelo/MG","Divinopolis/MG","Formiga/MG","Frutal/MG","Governador Valadares/MG","Ipatinga/MG","Itabira/MG","Itajuba/MG","Ituiutaba/MG","Joao Monlevade/MG","Juiz de Fora/MG","Lavras/MG","Manhuacu/MG","Montes Claros/MG","Muriae/MG","Nova Lima/MG","Patos de Minas/MG","Patrocinio/MG","Pocos de Caldas/MG","Ponte Nova/MG","Ribeirao das Neves/MG","Sabara/MG","Santa Luzia/MG","Sete Lagoas/MG","Teofilo Otoni/MG","Timoteo/MG","Uberaba/MG","Uberlandia/MG","Uba/MG","Varginha/MG","Vicosa/MG",
"Boa Vista/RR","Caracarai/RR","Rorainopolis/RR",
"Brasilia/DF","Ceilandia/DF","Gama/DF","Planaltina/DF","Samambaia/DF","Santa Maria/DF","Sobradinho/DF","Taguatinga/DF",
"Campo Grande/MS","Aquidauana/MS","Corumba/MS","Dourados/MS","Naviraí/MS","Nova Andradina/MS","Ponta Pora/MS","Tres Lagoas/MS",
"Cuiaba/MT","Alta Floresta/MT","Barra do Garças/MT","Caceres/MT","Colider/MT","Lucas do Rio Verde/MT","Rondonopolis/MT","Sinop/MT","Sorriso/MT","Tangara da Serra/MT","Varzea Grande/MT",
"Curitiba/PR","Almirante Tamandare/PR","Apucarana/PR","Araucaria/PR","Campo Largo/PR","Campo Mourao/PR","Cascavel/PR","Colombo/PR","Cornelio Procopio/PR","Foz do Iguacu/PR","Francisco Beltrao/PR","Guarapuava/PR","Londrina/PR","Maringa/PR","Paranagua/PR","Pinhais/PR","Ponta Grossa/PR","Sao Jose dos Pinhais/PR","Toledo/PR","Umuarama/PR",
"Florianopolis/SC","Ararangua/SC","Balneario Camboriu/SC","Blumenau/SC","Brusque/SC","Cacador/SC","Chapeco/SC","Concordia/SC","Criciuma/SC","Itajai/SC","Itapema/SC","Jaragua do Sul/SC","Joinville/SC","Lages/SC","Palhoca/SC","Rio do Sul/SC","Sao Jose/SC","Tubarao/SC","Videira/SC",
"Fortaleza/CE","Caucaia/CE","Crato/CE","Iguatu/CE","Itapipoca/CE","Juazeiro do Norte/CE","Maracanau/CE","Maranguape/CE","Quixada/CE","Sobral/CE",
"Goiania/GO",
"Joao Pessoa/PB","Bayeux/PB","Cabedelo/PB","Campina Grande/PB","Patos/PB","Santa Rita/PB","Sousa/PB",
"Macapa/AP","Laranjal do Jari/AP","Oiapoque/AP","Santana/AP",
"Maceio/AL","Arapiraca/AL","Palmeira dos Indios/AL","Penedo/AL","Uniao dos Palmares/AL",
"Manaus/AM","Coari/AM","Itacoatiara/AM","Manacapuru/AM","Parintins/AM","Tabatinga/AM","Tefé/AM",
"Natal/RN","Caico/RN","Mossoro/RN","Parnamirim/RN","Santa Cruz/RN",
"Palmas/TO","Araguaina/TO","Gurupi/TO","Porto Nacional/TO",
"Porto Alegre/RS","Alvorada/RS","Bage/RS","Bento Goncalves/RS","Cachoeirinha/RS","Canoas/RS","Caxias do Sul/RS","Erechim/RS","Gravatai/RS","Ijui/RS","Novo Hamburgo/RS","Passo Fundo/RS","Pelotas/RS","Rio Grande/RS","Santa Cruz do Sul/RS","Santa Maria/RS","Sao Leopoldo/RS","Uruguaiana/RS","Viamao/RS",
"Porto Velho/RO","Ariquemes/RO","Cacoal/RO","Ji-Parana/RO","Vilhena/RO",
"Recife/PE","Cabo de Santo Agostinho/PE","Caruaru/PE","Garanhuns/PE","Jaboatao dos Guararapes/PE","Olinda/PE","Paulista/PE","Petrolina/PE","Camaragibe/PE",
"Rio Branco/AC","Cruzeiro do Sul/AC","Sena Madureira/AC",
"Rio de Janeiro/RJ","Angra dos Reis/RJ","Belford Roxo/RJ","Cabo Frio/RJ","Campos dos Goytacazes/RJ","Duque de Caxias/RJ","Itaborai/RJ","Macae/RJ","Mage/RJ","Mesquita/RJ","Niteroi/RJ","Nova Friburgo/RJ","Nova Iguacu/RJ","Petropolis/RJ","Queimados/RJ","Resende/RJ","Sao Goncalo/RJ","Sao Joao de Meriti/RJ","Teresopolis/RJ","Volta Redonda/RJ",
"Salvador/BA","Alagoinhas/BA","Barreiras/BA","Camaçari/BA","Cruz das Almas/BA","Eunapolis/BA","Feira de Santana/BA","Ilheus/BA","Itabuna/BA","Itamaraju/BA","Jequie/BA","Juazeiro/BA","Lauro de Freitas/BA","Paulo Afonso/BA","Porto Seguro/BA","Serrinha/BA","Simoes Filho/BA","Teixeira de Freitas/BA","Vitoria da Conquista/BA",
"Sao Luis/MA","Acailandia/MA","Bacabal/MA","Balsas/MA","Caxias/MA","Codó/MA","Imperatriz/MA","Pinheiro/MA","Santa Ines/MA","Timon/MA",
"Sao Paulo/SP","Americana/SP","Araraquara/SP","Araras/SP","Barueri/SP","Bauru/SP","Botucatu/SP","Campinas/SP","Carapicuiba/SP","Cotia/SP","Diadema/SP","Embu das Artes/SP","Franca/SP","Guaruja/SP","Guarulhos/SP","Hortolandia/SP","Indaiatuba/SP","Itapecerica da Serra/SP","Itapevi/SP","Itaquaquecetuba/SP","Jundiai/SP","Limeira/SP","Marilia/SP","Maua/SP","Mogi das Cruzes/SP","Mogi Guacu/SP","Osasco/SP","Piracicaba/SP","Presidente Prudente/SP","Ribeirao Preto/SP","Rio Claro/SP","Santo Andre/SP","Santos/SP","Sao Bernardo do Campo/SP","Sao Caetano do Sul/SP","Sao Carlos/SP","Sao Jose do Rio Preto/SP","Sao Jose dos Campos/SP","Sao Vicente/SP","Sorocaba/SP","Sumare/SP","Suzano/SP","Taboao da Serra/SP","Taubate/SP",
"Teresina/PI","Floriano/PI","Parnaiba/PI","Picos/PI","Piripiri/PI",
"Vitoria/ES","Aracruz/ES","Cachoeiro de Itapemirim/ES","Cariacica/ES","Colatina/ES","Guarapari/ES","Linhares/ES","Sao Mateus/ES","Serra/ES","Vila Velha/ES"
]))
js = 'const CIDADES=' + __import__('json').dumps(cidades, ensure_ascii=False) + ';'
js += 'const dl=document.createElement("datalist");dl.id="cidades-br";'
js += 'CIDADES.forEach(c=>{const o=document.createElement("option");o.value=c;dl.appendChild(o)});'
js += 'document.body.appendChild(dl);'
with open(r'C:\Users\Windows 10\Downloads\VENNA_CRM\venna-crm\venna\static\cidades.js','w',encoding='utf-8') as f:
    f.write(js)
print('OK', len(cidades))
