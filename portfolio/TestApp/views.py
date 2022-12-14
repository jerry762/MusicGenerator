from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
# Create your views here.

from pathlib import Path
import json
import music21 as m21
import numpy as np
import tensorflow as tf
import random

APP_BASE_DIR = Path(__file__).resolve().parent
SAVA_MIDI_DIR = Path.joinpath(Path(__file__).resolve().parent.parent, 'static_test/music/output.mid')

MAPPINGS_PATH = [Path.joinpath(APP_BASE_DIR, 'mappings/mapping_Africa.json'),
                 Path.joinpath(APP_BASE_DIR, 'mappings/mapping_America.json'),
                 Path.joinpath(APP_BASE_DIR, 'mappings/mapping_British.json'),
                 Path.joinpath(APP_BASE_DIR, 'mappings/mapping_Canada.json'),
                 Path.joinpath(APP_BASE_DIR, 'mappings/mapping_China.json'),
                 Path.joinpath(APP_BASE_DIR, 'mappings/mapping_France.json'),
                 Path.joinpath(APP_BASE_DIR, 'mappings/mapping_Germany.json'),
                 Path.joinpath(APP_BASE_DIR, 'mappings/mapping_Ireland.json'),
                 Path.joinpath(APP_BASE_DIR, 'mappings/mapping_Luxembourg.json'),
                 Path.joinpath(APP_BASE_DIR, 'mappings/mapping_Pentatonic.json'),
                 Path.joinpath(APP_BASE_DIR, 'mappings/mapping_Poland.json')]


SAVE_LSTM_MODELS_PATH = [Path.joinpath(APP_BASE_DIR, 'models/model_Africa.h5'),
                         Path.joinpath(APP_BASE_DIR, 'models/model_America.h5'),
                         Path.joinpath(APP_BASE_DIR, 'models/model_British.h5'),
                         Path.joinpath(APP_BASE_DIR, 'models/model_Canada.h5'),
                         Path.joinpath(APP_BASE_DIR, 'models/model_China.h5'),
                         Path.joinpath(APP_BASE_DIR, 'models/model_France.h5'),
                         Path.joinpath(APP_BASE_DIR, 'models/model_Germany.h5'),
                         Path.joinpath(APP_BASE_DIR, 'models/model_Ireland.h5'),
                         Path.joinpath(APP_BASE_DIR, 'models/model_Luxembourg.h5'),
                         Path.joinpath(APP_BASE_DIR, 'models/model_Pentatonic.h5'),
                         Path.joinpath(APP_BASE_DIR, 'models/model_Poland.h5')]


SEQUENCE_LENGTH = 64


class MelodyGenerator:
    """A class that wraps the LSTM model and offers utilities to generate melodies."""

    def __init__(self, model_path, mapping_path):
        """Constructor that initialises TensorFlow model"""

        self.model_path = model_path
        self.model = tf.keras.models.load_model(model_path)

        with open(mapping_path, "r") as fp:
            self._mappings = json.load(fp)

        self._start_symbols = ["/"] * SEQUENCE_LENGTH

    def generate_melody(self, seed, num_steps, max_sequence_length, temperature):
        """Generates a melody using the DL model and returns a midi file.

        :param seed (str): Melody seed with the notation used to encode the dataset
        :param num_steps (int): Number of steps to be generated
        :param max_sequence_len (int): Max number of steps in seed to be considered for generation
        :param temperature (float): Float in interval [0, 1]. Numbers closer to 0 make the model more deterministic.
            A number closer to 1 makes the generation more unpredictable.

        :return melody (list of str): List with symbols representing a melody
        """

        # create seed with start symbols
        seed = seed.split()
        melody = seed
        seed = self._start_symbols + seed

        # map seed to int
        seed = [self._mappings[symbol] for symbol in seed]

        for _ in range(num_steps):

            # limit the seed to max_sequence_length
            seed = seed[-max_sequence_length:]

            # one-hot encode the seed
            onehot_seed = tf.keras.utils.to_categorical(seed, num_classes=len(self._mappings))
            # (1, max_sequence_length, num of symbols in the vocabulary)
            onehot_seed = onehot_seed[np.newaxis, ...]

            # make a prediction
            probabilities = self.model.predict(onehot_seed)[0]
            # [0.1, 0.2, 0.1, 0.6] -> 1
            output_int = self._sample_with_temperature(probabilities, temperature)

            # update seed
            seed.append(output_int)

            # map int to our encoding
            output_symbol = [k for k, v in self._mappings.items() if v == output_int][0]

            # check whether we're at the end of a melody
            if output_symbol == "/":
                break

            # update melody
            melody.append(output_symbol)

        return melody

    def _sample_with_temperature(self, probabilites, temperature):
        """Samples an index from a probability array reapplying softmax using temperature

        :param predictions (nd.array): Array containing probabilities for each of the possible outputs.
        :param temperature (float): Float in interval [0, 1]. Numbers closer to 0 make the model more deterministic.
            A number closer to 1 makes the generation more unpredictable.

        :return index (int): Selected output symbol
        """
        predictions = np.log(probabilites) / temperature
        probabilites = np.exp(predictions) / np.sum(np.exp(predictions))

        choices = range(len(probabilites))  # [0, 1, 2, 3]
        index = np.random.choice(choices, p=probabilites)

        return index

    def save_melody(self, melody, step_duration=0.25, format="midi", file_name=SAVA_MIDI_DIR):
        """Converts a melody into a MIDI file

        :param melody (list of str):
        :param min_duration (float): Duration of each time step in quarter length
        :param file_name (str): Name of midi file
        :return:
        """

        # create a music21 stream
        stream = m21.stream.Stream()

        start_symbol = None
        step_counter = 1

        # parse all the symbols in the melody and create note/rest objects
        for i, symbol in enumerate(melody):

            # handle case in which we have a note/rest
            if symbol != "_" or i + 1 == len(melody):

                # ensure we're dealing with note/rest beyond the first one
                if start_symbol is not None:

                    quarter_length_duration = step_duration * step_counter  # 0.25 * 4 = 1

                    # handle rest
                    if start_symbol == "r":
                        m21_event = m21.note.Rest(quarterLength=quarter_length_duration)

                    # handle note
                    else:
                        m21_event = m21.note.Note(int(start_symbol), quarterLength=quarter_length_duration)

                    stream.append(m21_event)

                    # reset the step counter
                    step_counter = 1

                start_symbol = symbol

            # handle case in which we have a prolongation sign "_"
            else:
                step_counter += 1

        # write the m21 stream to a midi file
        stream.write(format, file_name)


def test(request):
    return HttpResponse("hello world")


@csrf_exempt
def index(request):
    return render(request, 'index.html')


@csrf_exempt
def predict_lstm(request):
    if request.method == 'POST':
        key = int(request.POST.get('models'))
    else:
        print("Not catch the POST value")

    # print(SAVE_LSTM_MODELS_PATH[key])
    # print(MAPPINGS_PATH[key])

    mg = MelodyGenerator(SAVE_LSTM_MODELS_PATH[key], MAPPINGS_PATH[key])

    seeds = ["67 _ 67 _ 67 _ _ 65 64 _ 64 _ 64 _ _",
             "60 _ 60 _ 67 _ 67 _ 69 _ 69 _ 67 _",
             "67 _ 72 _ 67 _ 65 _ 67 _ _ _",
             "64 _ 62 _ 60 _ 62 _ 64 _ 64 _ 64 _",
             "60 _ 60 _ 67 _ 67 _ 69 _ 69 _ 67"]

    rand_int = random.randint(0, 4)

    melody = mg.generate_melody(seeds[rand_int], 500, SEQUENCE_LENGTH * 2, 0.3)
    mg.save_melody(melody)

    return render(request, 'generation.html')


@csrf_exempt
def music_dataset(request):
    return render(request, 'dataset.html')


@csrf_exempt
def music_generation(request):
    return render(request, 'generation.html')


@csrf_exempt
def music_home(request):
    return render(request, 'index.html')
