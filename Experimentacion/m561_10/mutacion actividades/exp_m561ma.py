from random import Random
import time
import inspyred
import numpy as np

import matplotlib.pyplot as plt

from pymoo.factory import get_performance_indicator

import csv

rand = Random()


class CromIterator:

    def __init__(self, cromosoma):
        self.cromosoma = cromosoma
        self.indice = 0

    def __next__(self):
        if self.indice < len(self.cromosoma.I):
            resultado = Cromosoma(self.cromosoma.I[self.indice], self.cromosoma.m[self.indice])
            self.indice += 1
            return resultado
        raise StopIteration

class Cromosoma:
    """ Modela la estructura que compete al cromosoma de nuestro AG,
        compuesto y sirviendo tambien como definicion del metodo inicializador.
            - Lista de claves aleatorias: usado para ver que actividad realizar a partir de las posibles, estadistica
            - Lista de modos: emparejado posicionalmente con la clave aleatoria, sirve para especificar el  modo de una actividad
    """

    def __init__(self, random_keys, modes):
        self.I = random_keys
        self.m = modes

    def __iter__(self):
        return CromIterator(self)

    def __getitem__(self, indice):
        return Cromosoma(self.I[indice], self.m[indice])

    def __setitem__(self, indice, valor):
        self.I[indice] = valor.I
        self.m[indice] = valor.m

    def __len__(self):
        return len(self.I)


def busca_posibles(realizadas, ejecutandose, lim_recursos, restrinciones):
    """ Busca las posibles, no contempla las ya realizadas y en_ejecucion
        Devuelve lista con las actividades que se pueden realizar
        Solo contempla las restinciones temporales
    """

    posibles = []

    for i in range(len(restrinciones)):
        sin_preced_completos = np.setdiff1d(restrinciones[i], realizadas)
        if sin_preced_completos.size == 0 and not i in realizadas and not i in ejecutandose:
            posibles.append(i)

    return posibles

def selecciona_actividad(posibles, I):
    """ Posible te dice los indices (actv) que puedes coger, e I para ordenar
    """
    I_posibles = np.array(I)[posibles]

    indx_max = np.argmax(I_posibles)
    return posibles[indx_max]

def es_factible(actividad, modo, recursos_en_uso, recursos_modo, lim_recursos):
    """ Comprueba si insertando actividad,modo en conjunto solucion da una solucion posible
    """

    factible = False

    #si no se esta ejecutando nada, se puede meter porque no existe modos inejecutables, si no, se comprueba si cabe
    if recursos_en_uso == []:
        factible = True
    else:
        #Se crea matriz con recursos en columna, se suma las filas y se comprueba que ninguno se exceda
        peticion = recursos_en_uso + [recursos_modo[actividad][modo]]
        suma = np.sum(peticion, axis = 0)
        factible = not np.any(suma > lim_recursos)


    return factible


def inserta_en_ejecucion(en_ejecucion, actividad, modo, recursos_modo, dias_modo):

    #Se añade actividad a la lista
    en_ejecucion["actividades"] = en_ejecucion["actividades"] + [actividad]

    en_ejecucion["recursos_en_uso"] = en_ejecucion["recursos_en_uso"] + [recursos_modo[actividad][modo]]

    en_ejecucion["dias_restantes"] = en_ejecucion["dias_restantes"] + [dias_modo[actividad][modo]]
    return en_ejecucion


def actualiza_dia(realizadas, en_ejecucion):


    end = len(en_ejecucion["dias_restantes"])
    i = 0
    while i < end:
        en_ejecucion["dias_restantes"][i] -= 1

        if en_ejecucion["dias_restantes"][i] == 0:
            realizadas = realizadas + [en_ejecucion["actividades"][i]]
            del en_ejecucion["dias_restantes"][i]
            del en_ejecucion["actividades"][i]
            del en_ejecucion["recursos_en_uso"][i]
            end -= 1 #Como hemos eliminado uno habra que iterar hasta una posicion menos!
        else:
            i += 1
    return [realizadas, en_ejecucion]



def decodifica(cromosoma, restrinciones, lim_recursos, recursos_modo, dias_modo):

    #Inicializacion
    en_ejecucion = {"actividades" : [], "recursos_en_uso" : [] , "dias_restantes" : []}
    realizadas = []
    dia_actual = 0
    solucion = [] #Lista de tuplas formato <actividad,dia_comienzo>

    #Mientras no se haya terminado todas...
    while len(realizadas) < len(cromosoma.I):
        #Se busca las posibles y se recorren todas las posibles
        posibles = busca_posibles(realizadas, en_ejecucion["actividades"], lim_recursos, restrinciones)

        while not len(posibles) == 0:
            actividad = selecciona_actividad(posibles, cromosoma.I)
            posibles.remove(actividad)

            #Se elige actv con mas probabilidad dentro de las posibles y no se contempla mas en el dia actual
            if es_factible(actividad, cromosoma.m[actividad], en_ejecucion["recursos_en_uso"], recursos_modo, lim_recursos):
                #Si es factible, se agrega a solucion con el dia de comienzo y se inserta en tabla en_ejecucion
                solucion.append((actividad, dia_actual))
                en_ejecucion = inserta_en_ejecucion(en_ejecucion, actividad, cromosoma.m[actividad], recursos_modo, dias_modo)


        dia_actual += 1
        [realizadas, en_ejecucion] = actualiza_dia(realizadas, en_ejecucion)

    return solucion


class Problema(inspyred.benchmarks.Benchmark):

    def __init__(self, recursos_modo, dias_modo, lim_recursos, Mn, restrinciones, coste_fijo, coste_rnr, rnr_modo, objetivos = 2):

        inspyred.benchmarks.Benchmark.__init__(self, len(Mn), objetivos)

        self.recursos_modo = recursos_modo
        self.dias_modo = dias_modo
        self.lim_recursos = lim_recursos
        self.Mn = Mn
        self.restrinciones = restrinciones


        #Calculamos el coste de cada modo según su gasto de recursos no renovables y su coste fijo
        coste_modo = np.array([np.array(i)*coste_rnr for i in np.array(rnr_modo)])
        coste_modo = [np.sum(i, axis=1).tolist() for i in coste_modo]

        for i in range(len(coste_modo)):
            coste_modo[i] = (np.array(coste_modo[i]) + np.array(coste_fijo[i])).tolist()

        self.coste_modo = coste_modo

        self.preprocesamiento()

        #Tmax y Tmin la suma de los tiempos de las actividades con su modo mas largo y el mas corto respectivamente
        self.Tmax = sum([max(self.dias_modo[i]) for i in range(len(self.dias_modo))])
        self.Tmin = max([min(self.dias_modo[i]) for i in range(len(self.dias_modo))])

        #Cmax y Cmin la suma de los costes de las actividades con su modo mas costoso y el menos costoso respectivamente
        self.Cmax = sum([max(self.coste_modo[i]) for i in range(len(self.coste_modo))])
        self.Cmin = sum([min(self.coste_modo[i]) for i in range(len(self.coste_modo))])

        #self.maximize = True
        self.maximize = False

        print("Se crea el problema!")

    def preprocesamiento(self):
        #Mientras se haga un cambio, o la primera vez, se hace
        Flag_changes = True

        while(Flag_changes):
            #Primero modos no-ejecutable
            f_ene, self.recursos_modo, self.dias_modo, self.coste_modo = self.elimina_no_ejecutables()

            #Segundo resources-redudants
            f_err, self.recursos_modo, self.lim_recursos  = self.elimina_recursos_redundantes()

            #Tercero modos inefficient
            f_ei, self.recursos_modo, self.dias_modo, self.coste_modo = self.elimina_ineficientes()

            if(not f_ene or not f_err or not f_ei):
                Flag_changes = False

        self.Mn = [len(self.dias_modo[i]) for i in range(len(self.dias_modo))]
        return 0

    def elimina_no_ejecutables(self):
        """ Esta version no usa numpy. Recorre todos los modos de todas las actividades, si alguno de los recursos de dicha
            actividad-modo es mayor que el limite, ese modo sera inejecutable y deberá ser borrado y se actualizarán las demás
            variables relacionadas con él
        """
        nuevo_recursos_modo = []
        nuevo_dias_modo = []
        nuevo_coste_modo = []

        flag_cambio = False
        for actv, modos in enumerate(self.recursos_modo):
            nuevo_recursos_modo.append([])
            nuevo_dias_modo.append([])
            nuevo_coste_modo.append([])

            for modo, recursos in enumerate(modos):

                if (np.array(self.recursos_modo[actv][modo]) <= np.array(self.lim_recursos)).all():
                    nuevo_recursos_modo[actv].append(self.recursos_modo[actv][modo])
                    nuevo_dias_modo[actv].append(self.dias_modo[actv][modo])
                    nuevo_coste_modo[actv].append(self.coste_modo[actv][modo])
                else:
                    flag_cambio = True
        return flag_cambio, nuevo_recursos_modo, nuevo_dias_modo, nuevo_coste_modo



    def elimina_recursos_redundantes(self):
        """ Sean recursos redundantes aquellos para los que ni realizando todas las actividades con su modo mas costoso para
        determinado recurso se vean agotados
        """
        #_Cogemos el mayor gasto de cada modo para todos los recursos
        max_sum_resources = np.sum([np.max(np.array(self.recursos_modo[i]), 0) for i in range(len(self.recursos_modo))], 0)
        #Vemos aquellos recursos que no sean redundantes
        index_ok = max_sum_resources > np.array(self.lim_recursos)

        if not index_ok.all(): #Si ninguno es redundante no se cambia nada
            nuevo_recursos_modo = []
            for i in range(len(self.recursos_modo)):
                nuevo_recursos_modo.append([])
                for j in range(len(self.recursos_modo[i])):
                    nuevo_recursos_modo[i].append((np.array(self.recursos_modo[i][j])[index_ok]).tolist())

            nuevo_lim_recursos = np.array(self.lim_recursos)[index_ok].tolist()
            cambios = True

        else:
            nuevo_lim_recursos = self.lim_recursos
            nuevo_recursos_modo = self.recursos_modo
            cambios = False


        return cambios, nuevo_recursos_modo, nuevo_lim_recursos


    def elimina_ineficientes(self):
        """ Elimina los modos ineficientes, siendo estos aquellos que necesitan mayor cantidad de recursos,
            para todos los tipos de recurso, y además tienen mayor duración que otro modo para la misma
            actividad.
        """
        #Estructuras donde reconstruir
        new_recursos_modo = []
        new_dias_modo = []
        new_coste_modo = []

        cambios = False

        #Iteramos todas las actividades, y si hay mas de un modo de realizarla se saca el modo de mayor duracion
        #y se comprueba que no consuma mas recursos que el resto de modos para esa actividad
        for actividad, dias in enumerate(self.dias_modo):
            new_recursos_modo.append([])
            new_dias_modo.append([])
            new_coste_modo.append([])

            if len(dias) > 1: #Si hay mas de un modo por dia
                #Se coge el dia con mas duracion y se ve los recursos que gasta para compararlo con los demas
                modo_mas_largo = np.argmax(dias)

                recursos_mas_largo = self.recursos_modo[actividad][modo_mas_largo]

                ineficiente = True

                #Aqui se guarda el resto sin contar el modo de mas duracion, se hace uso de estrucutras array para comprobarlo
                #facilmente
                resto = np.delete(self.recursos_modo[actividad], modo_mas_largo, axis=0)
                ineficiente = not (resto > recursos_mas_largo).any()

                if ineficiente:
                    cambios = True
                    new_recursos_modo[actividad].append(resto.tolist())
                    new_dias_modo[actividad].append(np.delete(self.dias_modo[actividad], modo_mas_largo).tolist())
                    new_coste_modo[actividad].append(np.delete(self.coste_modo[actividad], modo_mas_largo).tolist())
                else:
                    new_recursos_modo[actividad].append(self.recursos_modo[actividad])
                    new_dias_modo[actividad].append(self.dias_modo[actividad])
                    new_coste_modo[actividad].append(self.coste_modo[actividad])
            else:

                new_recursos_modo[actividad].append(self.recursos_modo[actividad])
                new_dias_modo[actividad].append(self.dias_modo[actividad])
                new_coste_modo[actividad].append(self.coste_modo[actividad])


        return cambios, np.squeeze(new_recursos_modo).tolist(), np.squeeze(new_dias_modo).tolist(), np.squeeze(new_coste_modo).tolist()


    def genera_candidato(self, random, args):
        """ Genera aleatoriamente cromosoma, compuestos por su random-key + modos
        """

        num_acts = len(self.recursos_modo)
        rk_acts = [random.random() for _ in range(num_acts)]
        rk_modos = [random.randint(0, self.Mn[i]-1) for i in range(num_acts)]

        return Cromosoma(rk_acts, rk_modos)


    def mutacion(self, random, candidates, args):

        prob_mutacion = args.setdefault('mutation_rate', 0.1)

        #Para cada individuo
        for it, cromosoma in enumerate(candidates):

            #Se elige actividad aleatoria
            actv_i = random.randint(0, len(cromosoma.I) - 1)
            #otra aleatoria
            actv_j = random.randint(0, len(cromosoma.I) - 1)

            #que sean distintas
            while (actv_i == actv_j and len(cromosoma.I)>2):
                actv_j = random.randint(0, len(cromosoma.I) - 1)


            if random.random() < prob_mutacion:

                i_aux = cromosoma.I[actv_i]
                cromosoma.I[actv_i] = cromosoma.I[actv_j]
                cromosoma.I[actv_j] = i_aux

        return candidates



    def makespan(self, cromosoma):
        """Decodifica la solución y sabemos que si LFTj es el día de finalización de cada activididad,
        el mayor de este conjunto será el makespan
        """
        sol = decodifica(cromosoma, self.restrinciones, self.lim_recursos, self.recursos_modo, self.dias_modo) #Aki fallo

        dia_finalizacion = []

        for i, actv_dia in enumerate(sol):
            dia_finalizacion.append(actv_dia[1]+self.dias_modo[actv_dia[0]][cromosoma.m[actv_dia[0]]])

        makespan = max(dia_finalizacion)

        return makespan


    def calcula_coste(self, cromosoma):
        coste = 0
        for actv, modo in enumerate (cromosoma.m):
            coste += self.coste_modo[actv][modo]
        return coste



    def evaluador(self, candidates, args):
        fitness = []
        for cromosoma in candidates:

            obj1 = self.makespan(cromosoma)

            obj2 = self.calcula_coste(cromosoma)

            fitness.append(inspyred.ec.emo.Pareto([obj1, obj2]))


        return fitness


    def f_eval_tiempo_maximizacion(self, cromosoma):
        """ Funcion evaluacion para tiempo. Funcion rampa para maximizacion y usar roulette wheel
        """
        t_proyecto = self.makespan(cromosoma)
        t_evaluado = (self.Tmax - t_proyecto) / (self.Tmax - self.Tmin)

        return t_evaluado


    def f_eval_coste_maximizacion(self, cromosoma):
        """ Funcion evaluacion para coste.  Funcion rampa para maximizacion y usar roulette wheel
        """
        coste_proyecto = self.calcula_coste(cromosoma)
        coste_evaluado = (self.Cmax - coste_proyecto) / (self.Cmax - self.Cmin)

        return coste_evaluado


    def evaluador_maximizacion(self, candidates, args):
        fitness = []
        for cromosoma in candidates:

            obj1 = self.f_eval_tiempo_maximizacion(cromosoma)

            obj2 = self.f_eval_coste_maximizacion(cromosoma)

            fitness.append(inspyred.ec.emo.Pareto([obj1, obj2]))

        print("Calculao los fitness!")
        return fitness


    def observador_real(self, population, num_generations, num_evaluations, args):

        print("Generacion numero: ", num_generations)



#m561_10
restrinciones = [[],[],[],[0],[3],[1,4],[3],[1],[1,3],[5,6,7],[2,7],[2,7],[2,5,6],[0,10,11],[0,10,11],[8,9,12]]

lim_recursos = [15, 15]

recursos_modo =[
    [
        [5, 5],
        [5, 5],
        [5, 5],
        [4, 5],
        [4, 5]
    ],
    [
        [5,10],
        [4,8],
        [4,6],
        [3,6],
        [3,3]
    ],
    [
        [9,9],
        [6,8],
        [6,8],
        [3,7],
        [4,6]
    ],
    [
        [9,8],
        [7,8],
        [6,8],
        [3,6],
        [3,5]
    ],
    [
        [10,9],
        [9,9],
        [9,6],
        [9,6],
        [8,4]
    ],
    [
        [9,5],
        [7,4],
        [8,4],
        [7,3],
        [5,2]
    ],
    [
        [8,10],
        [8,7],
        [7,8],
        [7,7],
        [6,6]
    ],
    [
        [7,9],
        [6,9],
        [4,8],
        [3,7],
        [4,7]
    ],
    [
        [4,9],
        [3,9],
        [3,8],
        [2,8],
        [2,8]
    ],
    [
        [8,2],
        [8,2],
        [7,2],
        [6,2],
        [4,2]
    ],
    [
        [19,9],
        [10,7],
        [10,8],
        [9,4],
        [9,1]
    ],
    [
        [7,2],
        [7,2],
        [6,2],
        [6,1],
        [5,1]
    ],
    [
        [5,7],
        [4,7],
        [4,5],
        [3,5],
        [2,3]
    ],
    [
        [8,9],
        [10,9],
        [7,9],
        [5,6],
        [4,7]
    ],
    [
        [9,6],
        [9,6],
        [7,5],
        [6,5],
        [4,5]
    ],
    [
        [7,5],
        [7,4],
        [6,4],
        [6,4],
        [7,4]
    ]
]

dias_modo = [
    [3,4,4,7,9],
    [3,4,5,6,9],
    [1,2,4,8,8],
    [2,2,6,8,8],
    [1,4,5,8,9],
    [3,7,7,8,10],
    [2,4,4,5,6],
    [4,5,6,10,10],
    [1,4,5,8,10],
    [2,5,5,7,9],
    [1,4,4,8,9],
    [2,3,5,9,10],
    [2,4,7,8,10],
    [2,2,4,5,5],
    [1,2,5,8,9],
    [1,2,4,4,4]
]

coste_rnr = [19,13]

rnr_modo = [
    [
        [8,10],
        [6,10],
        [7,9],
        [5,9],
        [3,8]
    ],
    [
        [3,10],
        [3,10],
        [2,10],
        [1,9],
        [1,9]
    ],
    [
        [10,5],
        [9,5],
        [9,2],
        [7,1],
        [7,1]
    ],
    [
        [9,4],
        [10,4],
        [9,4],
        [6,4],
        [7,4]
    ],
    [
        [9,10],
        [9,10],
        [8,10],
        [8,9],
        [7,9]
    ],
    [
        [7,10],
        [7,8],
        [7,6],
        [7,5],
        [6,4]
    ],
    [
        [5,9],
        [4,7],
        [5,8],
        [4,7],
        [2,5]
    ],
    [
        [9,10],
        [7,8],
        [6,5],
        [5,4],
        [4,4]
    ],
    [
        [9,8],
        [9,8],
        [8,7],
        [8,7],
        [7,5]
    ],
    [
        [6,8],
        [6,6],
        [6,7],
        [3,5],
        [2,4]
    ],
    [
        [9,2],
        [8,2],
        [7,2],
        [6,2],
        [6,2]
    ],
    [
        [7,6],
        [6,6],
        [6,5],
        [5,5],
        [4,4]
    ],
    [
        [6,4],
        [5,4],
        [5,3],
        [5,2],
        [4,2]
    ],
    [
        [7,9],
        [8,7],
        [7,7],
        [5,6],
        [6,5]
    ],
    [
        [4,5],
        [3,5],
        [2,4],
        [2,2],
        [1,1]
    ],
    [
        [9,3],
        [7,3],
        [3,3],
        [5,2],
        [4,2]
    ]
]

coste_fijo = [
    [300,350,375,410,450],
    [130,140,150,160,189],
    [40,30,70,100,95],
    [20,20,40,65,70],
    [100,140,150,180,169],
    [30,55,55,60,80],
    [120,140,145,165,140],
    [40,50,60,80,85],
    [20,48,65,75,90],
    [25,35,38,50,70],
    [100,135,140,168,185],
    [200,300,400,500,550],
    [40,75,100,90,110],
    [300,300,440,500,500],
    [120,145,175,200,220],
    [100,130,150,155,145]
]

Mn = [[5],[5],[5],[5],[5],[5],[5],[5],[5],[5],[5],[5],[5],[5],[5],[5]]




problem = Problema(recursos_modo, dias_modo, lim_recursos, Mn, restrinciones, coste_fijo, coste_rnr, rnr_modo, objetivos = 2)

algoritmo_nsgadefault = inspyred.ec.emo.NSGA2(rand)

algoritmo_nsgadefault.observer = problem.observador_real
algoritmo_nsgadefault.terminator = inspyred.ec.terminators.generation_termination
#algoritmo.selector = inspyred.ec.selectors.rank_selection
algoritmo_nsgadefault.variator = [inspyred.ec.variators.uniform_crossover, problem.mutacion]


print("Se ajusta el algoritmo")

n_experimentos = 10


soluciones_nsgadefault_mr01 = []

algor = 1

print("Algoritmo ",algor)

with open('nsgadefault_mr01.csv', mode='w') as f_csv_1:
    csv_writer_1 = csv.writer(f_csv_1, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    csv_writer_1.writerow(["tiempo", "coste"])

    #NSGAII default con mutation_rate = 0.1
    for i in range(n_experimentos):
        print("Experimento ",i," de algoritmo ",algor)


        final_pop = algoritmo_nsgadefault.evolve(generator=problem.genera_candidato,
                                    evaluator=problem.evaluador,
                                    pop_size=100,
                                    maximize=False,
                                    #num_selected=100, # rank_selection y tournament numero de individuos para ser seleccionados (default 1)
                                    #tournament_size=20, para tournament selection default 2
                                    #num_elites=10, para generational y random replacement
                                    mutation_rate=0.1,
                                    max_evaluations=100,
                                    max_generations = 100
                                    )

        soluciones_nsgadefault_mr01.append(final_pop)

        for _, indiv in enumerate(final_pop):
            csv_writer_1.writerow([indiv.fitness[0], indiv.fitness[1]])


soluciones_nsgadefault_mr02 = []

algor += 1

print("Algoritmo ",algor)

#NSGAII default con mutation_rate = 0.2
problem = Problema(recursos_modo, dias_modo, lim_recursos, Mn, restrinciones, coste_fijo, coste_rnr, rnr_modo, objetivos = 2)

with open('nsgadefault_mr02.csv', mode='w') as f_csv_2:
    csv_writer_2 = csv.writer(f_csv_2, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    csv_writer_2.writerow(["tiempo", "coste"])

    for i in range(n_experimentos):
        print("Experimento ",i," de algoritmo ",algor)

        final_pop = algoritmo_nsgadefault.evolve(generator=problem.genera_candidato,
                                    evaluator=problem.evaluador,
                                    pop_size=100,
                                    maximize=False,
                                    #num_selected=100, # rank_selection y tournament numero de individuos para ser seleccionados (default 1)
                                    #tournament_size=20, para tournament selection default 2
                                    #num_elites=10, para generational y random replacement
                                    mutation_rate=0.2,
                                    max_evaluations=100,
                                    max_generations = 100
                                    )

        soluciones_nsgadefault_mr02.append(final_pop)

        for _, indiv in enumerate(final_pop):
            csv_writer_2.writerow([indiv.fitness[0], indiv.fitness[1]])


#NSGAII con rank selection y mutation_rate = 0.1
problem = Problema(recursos_modo, dias_modo, lim_recursos, Mn, restrinciones, coste_fijo, coste_rnr, rnr_modo, objetivos = 2)


algoritmo_rankselection = inspyred.ec.emo.NSGA2(rand)
algoritmo_rankselection.observer = problem.observador_real
algoritmo_rankselection.terminator = inspyred.ec.terminators.generation_termination
algoritmo_rankselection.selector = inspyred.ec.selectors.rank_selection
algoritmo_rankselection.variator = [inspyred.ec.variators.uniform_crossover, problem.mutacion]


print("Se ajusta el algoritmo")

algor += 1

print("Algoritmo ",algor)

soluciones_rankselection = []

with open('rankselection.csv', mode='w') as f_csv_3:
    csv_writer_3 = csv.writer(f_csv_3, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    csv_writer_3.writerow(["tiempo", "coste"])

    for i in range(n_experimentos):
        print("Experimento ",i," algoritmo ",algor)


        final_pop = algoritmo_rankselection.evolve(generator=problem.genera_candidato,
                                    evaluator=problem.evaluador,
                                    pop_size=100,
                                    maximize=False,
                                    num_selected=100, # rank_selection y tournament numero de individuos para ser seleccionados (default 1)
                                    #tournament_size=20, para tournament selection default 2
                                    #num_elites=10, para generational y random replacement
                                    mutation_rate=0.1,
                                    max_evaluations=100,
                                    max_generations = 100
                                    )

        soluciones_rankselection.append(final_pop)

        for _, indiv in enumerate(final_pop):
            csv_writer_3.writerow([indiv.fitness[0], indiv.fitness[1]])

#NSGA replacement
problem = Problema(recursos_modo, dias_modo, lim_recursos, Mn, restrinciones, coste_fijo, coste_rnr, rnr_modo, objetivos = 2)

algoritmo_nsgareplacement = inspyred.ec.emo.NSGA2(rand)

algoritmo_nsgareplacement.observer = problem.observador_real
algoritmo_nsgareplacement.terminator = inspyred.ec.terminators.generation_termination
algoritmo_nsgareplacement.replacement = inspyred.ec.replacers.nsga_replacement
algoritmo_nsgareplacement.variator = [inspyred.ec.variators.uniform_crossover, problem.mutacion]


print("Se ajusta el algoritmo")

algor += 1

print("Algoritmo ",algor)

soluciones_nsga_rep = []
with open('nsga_rep.csv', mode='w') as f_csv_4:
    csv_writer_4 = csv.writer(f_csv_4, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    csv_writer_4.writerow(["tiempo", "coste"])

    for i in range(n_experimentos):
        print("Experimento ",i," de algoritmo ",algor)

        final_pop = algoritmo_nsgareplacement.evolve(generator=problem.genera_candidato,
                                    evaluator=problem.evaluador,
                                    pop_size=100,
                                    maximize=False,
                                    #num_selected=100, # rank_selection y tournament numero de individuos para ser seleccionados (default 1)
                                    #tournament_size=20, para tournament selection default 2
                                    #num_elites=10, para generational y random replacement
                                    mutation_rate=0.1,
                                    max_evaluations=100,
                                    max_generations = 100
                                    )

        soluciones_nsga_rep.append(final_pop)

        for _, indiv in enumerate(final_pop):
            csv_writer_4.writerow([indiv.fitness[0], indiv.fitness[1]])


#NSGA replacement y rank rank_selection
problem = Problema(recursos_modo, dias_modo, lim_recursos, Mn, restrinciones, coste_fijo, coste_rnr, rnr_modo, objetivos = 2)

algoritmo_nsgareplacemente_rank_selection = inspyred.ec.emo.NSGA2(rand)

algoritmo_nsgareplacemente_rank_selection.observer = problem.observador_real
algoritmo_nsgareplacemente_rank_selection.terminator = inspyred.ec.terminators.generation_termination
algoritmo_nsgareplacemente_rank_selection.replacement = inspyred.ec.replacers.nsga_replacement
algoritmo_nsgareplacemente_rank_selection.variator = [inspyred.ec.variators.uniform_crossover, problem.mutacion]
algoritmo_nsgareplacemente_rank_selection.selector = inspyred.ec.selectors.rank_selection

print("Se ajusta el algoritmo")

algor += 1

print("Algoritmo ",algor)

soluciones_nsga_rep_rank = []
with open('nsga_rep_rank.csv', mode='w') as f_csv_5:
    csv_writer_5 = csv.writer(f_csv_5, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    csv_writer_5.writerow(["tiempo", "coste"])

    for i in range(n_experimentos):
        print("Experimento ",i," de algoritmo ",algor)


        final_pop = algoritmo_nsgareplacemente_rank_selection.evolve(generator=problem.genera_candidato,
                                    evaluator=problem.evaluador,
                                    pop_size=100,
                                    maximize=False,
                                    num_selected=100, # rank_selection y tournament numero de individuos para ser seleccionados (default 1)
                                    #tournament_size=20, para tournament selection default 2
                                    #num_elites=10, para generational y random replacement
                                    mutation_rate=0.1,
                                    max_evaluations=100,
                                    max_generations = 100
                                    )

        soluciones_nsga_rep_rank.append(final_pop)

        for _, indiv in enumerate(final_pop):
            csv_writer_5.writerow([indiv.fitness[0], indiv.fitness[1]])

#NSGA default con crossover n point = 1
problem = Problema(recursos_modo, dias_modo, lim_recursos, Mn, restrinciones, coste_fijo, coste_rnr, rnr_modo, objetivos = 2)

algoritmo_crossover_1_point = inspyred.ec.emo.NSGA2(rand)

algoritmo_crossover_1_point.observer = problem.observador_real
algoritmo_crossover_1_point.terminator = inspyred.ec.terminators.generation_termination
#algoritmo.selector = inspyred.ec.selectors.rank_selection
algoritmo_crossover_1_point.variator = [inspyred.ec.variators.n_point_crossover, problem.mutacion]


print("Se ajusta el algoritmo")

algor += 1

print("Algoritmo ",algor)

soluciones_crossover_1_point = []

with open('crossover_1_point.csv', mode='w') as f_csv_6:
    csv_writer_6 = csv.writer(f_csv_6, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    csv_writer_6.writerow(["tiempo", "coste"])

    for i in range(n_experimentos):
        print("Experimento ",i," de algoritmo ",algor)


        final_pop = algoritmo_crossover_1_point.evolve(generator=problem.genera_candidato,
                                    evaluator=problem.evaluador,
                                    pop_size=100,
                                    maximize=False,
                                    #num_selected=100, # rank_selection y tournament numero de individuos para ser seleccionados (default 1)
                                    #tournament_size=20, para tournament selection default 2
                                    #num_elites=10, para generational y random replacement
                                    mutation_rate=0.1,
                                    max_evaluations=100,
                                    num_crossover_points = 1,
                                    max_generations = 100
                                    )

        soluciones_crossover_1_point.append(final_pop)

        for _, indiv in enumerate(final_pop):
            csv_writer_6.writerow([indiv.fitness[0], indiv.fitness[1]])

#NSGA default con crossover n point = 2
problem = Problema(recursos_modo, dias_modo, lim_recursos, Mn, restrinciones, coste_fijo, coste_rnr, rnr_modo, objetivos = 2)

algoritmo_crossover_2_point = inspyred.ec.emo.NSGA2(rand)

algoritmo_crossover_2_point.observer = problem.observador_real
algoritmo_crossover_2_point.terminator = inspyred.ec.terminators.generation_termination
#algoritmo.selector = inspyred.ec.selectors.rank_selection
algoritmo_crossover_2_point.variator = [inspyred.ec.variators.n_point_crossover, problem.mutacion]


print("Se ajusta el algoritmo")

algor += 1

print("Algoritmo ", algor)

soluciones_crossover_2_point = []

with open('crossover_2_point.csv', mode='w') as f_csv_7:
    csv_writer_7 = csv.writer(f_csv_7, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    csv_writer_7.writerow(["tiempo", "coste"])

    for i in range(n_experimentos):
        print("Experimento ",i," de algoritmo ",algor)


        final_pop = algoritmo_crossover_2_point.evolve(generator=problem.genera_candidato,
                                    evaluator=problem.evaluador,
                                    pop_size=100,
                                    maximize=False,
                                    #num_selected=100, # rank_selection y tournament numero de individuos para ser seleccionados (default 1)
                                    #tournament_size=20, para tournament selection default 2
                                    #num_elites=10, para generational y random replacement
                                    mutation_rate=0.1,
                                    max_evaluations=100,
                                    num_crossover_points = 2,
                                    max_generations = 100
                                    )

        soluciones_crossover_2_point.append(final_pop)

        for _, indiv in enumerate(final_pop):
            csv_writer_7.writerow([indiv.fitness[0], indiv.fitness[1]])

#NSGA selection rank y crossover 1 point
problem = Problema(recursos_modo, dias_modo, lim_recursos, Mn, restrinciones, coste_fijo, coste_rnr, rnr_modo, objetivos = 2)

algoritmo_crossover_1_point_rank_selection = inspyred.ec.emo.NSGA2(rand)

algoritmo_crossover_1_point_rank_selection.observer = problem.observador_real
algoritmo_crossover_1_point_rank_selection.terminator = inspyred.ec.terminators.generation_termination
algoritmo_crossover_1_point_rank_selection.selector = inspyred.ec.selectors.rank_selection
algoritmo_crossover_1_point_rank_selection.variator = [inspyred.ec.variators.n_point_crossover, problem.mutacion]


print("Se ajusta el algoritmo")

algor += 1

print("Algoritmo ",algor)

soluciones_crossover_1_point_rank_selection = []

with open('crossover_1_point_rank_selection.csv', mode='w') as f_csv_8:
    csv_writer_8 = csv.writer(f_csv_8, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    csv_writer_8.writerow(["tiempo", "coste"])

    for i in range(n_experimentos):
        print("Experimento ",i," de algoritmo ",algor)


        final_pop = algoritmo_crossover_1_point_rank_selection.evolve(generator=problem.genera_candidato,
                                    evaluator=problem.evaluador,
                                    pop_size=100,
                                    maximize=False,
                                    num_selected=100, # rank_selection y tournament numero de individuos para ser seleccionados (default 1)
                                    #tournament_size=20, para tournament selection default 2
                                    #num_elites=10, para generational y random replacement
                                    mutation_rate=0.1,
                                    max_evaluations=100,
                                    num_crossover_points = 1,
                                    max_generations = 100
                                    )

        soluciones_crossover_1_point_rank_selection.append(final_pop)

        for _, indiv in enumerate(final_pop):
            csv_writer_8.writerow([indiv.fitness[0], indiv.fitness[1]])

#NSGA replacement y crossover 1 point
problem = Problema(recursos_modo, dias_modo, lim_recursos, Mn, restrinciones, coste_fijo, coste_rnr, rnr_modo, objetivos = 2)

algoritmo_crossover_1_point_nsgarep = inspyred.ec.emo.NSGA2(rand)

algoritmo_crossover_1_point_nsgarep.observer = problem.observador_real
algoritmo_crossover_1_point_nsgarep.terminator = inspyred.ec.terminators.generation_termination
algoritmo_crossover_1_point_nsgarep.replacement = inspyred.ec.replacers.nsga_replacement
algoritmo_crossover_1_point_nsgarep.variator = [inspyred.ec.variators.n_point_crossover, problem.mutacion]


print("Se ajusta el algoritmo")

algor += 1

print("Algoritmo ", algor)

soluciones_crossover_1_point_nsgarep = []

with open('crossover_1_point_nsgarep.csv', mode='w') as f_csv_9:
    csv_writer_9 = csv.writer(f_csv_9, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    csv_writer_9.writerow(["tiempo", "coste"])

    for i in range(n_experimentos):
        print("Experimento ",i," de algoritmo ",algor)


        final_pop = algoritmo_crossover_1_point_nsgarep.evolve(generator=problem.genera_candidato,
                                    evaluator=problem.evaluador,
                                    pop_size=100,
                                    maximize=False,
                                    #num_selected=100, # rank_selection y tournament numero de individuos para ser seleccionados (default 1)
                                    #tournament_size=20, para tournament selection default 2
                                    #num_elites=10, para generational y random replacement
                                    mutation_rate=0.1,
                                    max_evaluations=100,
                                    num_crossover_points = 1,
                                    max_generations = 100
                                    )

        soluciones_crossover_1_point_nsgarep.append(final_pop)

        for _, indiv in enumerate(final_pop):
            csv_writer_9.writerow([indiv.fitness[0], indiv.fitness[1]])

#NSGA replacement rank selection y crossover 1 point
problem = Problema(recursos_modo, dias_modo, lim_recursos, Mn, restrinciones, coste_fijo, coste_rnr, rnr_modo, objetivos = 2)

algoritmo_crossover_1_point_nsgarep_rank_selection = inspyred.ec.emo.NSGA2(rand)

algoritmo_crossover_1_point_nsgarep_rank_selection.observer = problem.observador_real
algoritmo_crossover_1_point_nsgarep_rank_selection.terminator = inspyred.ec.terminators.generation_termination
algoritmo_crossover_1_point_nsgarep_rank_selection.replacement = inspyred.ec.replacers.nsga_replacement
algoritmo_crossover_1_point_nsgarep_rank_selection.variator = [inspyred.ec.variators.n_point_crossover, problem.mutacion]
algoritmo_crossover_1_point_nsgarep_rank_selection.selector = inspyred.ec.selectors.rank_selection

print("Se ajusta el algoritmo")

algor += 1

print("Algoritmo ",algor)

soluciones_crossover_1_point_nsgarep_rank_selection = []

with open('crossover_1_point_nsgarep_rank_selection.csv', mode='w') as f_csv_10:
    csv_writer_10 = csv.writer(f_csv_10, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    csv_writer_10.writerow(["tiempo", "coste"])

    for i in range(n_experimentos):
        print("Experimento ",i," de algoritmo ",algor)


        final_pop = algoritmo_crossover_1_point_nsgarep.evolve(generator=problem.genera_candidato,
                                    evaluator=problem.evaluador,
                                    pop_size=100,
                                    maximize=False,
                                    num_selected=100, # rank_selection y tournament numero de individuos para ser seleccionados (default 1)
                                    #tournament_size=20, para tournament selection default 2
                                    #num_elites=10, para generational y random replacement
                                    mutation_rate=0.1,
                                    max_evaluations=100,
                                    num_crossover_points = 1,
                                    max_generations = 100
                                    )

        soluciones_crossover_1_point_nsgarep_rank_selection.append(final_pop)

        for _, indiv in enumerate(final_pop):
            csv_writer_10.writerow([indiv.fitness[0], indiv.fitness[1]])
