import shutil
import subprocess
import sys
import csv
import fileinput
import re

import constants
import graph
import predict

def train(output_graphs, data=None, note=None):
    print("Training data, generating graphs: %r" % output_graphs)

    _copy_original_model()
    _run_trainer()

    _generate_parsed_logs()
    (training_details, validation_details) = _parse_logs()

    if output_graphs:
        graph.plot_results(training_details, validation_details, note)
        #predict.test_validation()

def _copy_original_model():
    """
    Copies the non-fine tuned AlexNet model to a new weight file so we can fine tune it, keeping
    the original unchanged for multiple test runs.
    """

    print "\tCopying original, non-finetuned weight model over for training..."
    shutil.rmtree(constants.WEIGHTS_FINETUNED, ignore_errors=True)
    shutil.copyfile(constants.WEIGHTS_NON_FINETUNED, constants.WEIGHTS_FINETUNED)

def _run_trainer():
    """
    Runs Caffe to train the model.
    """
    print("\tRunning trainer...")
    with open(constants.OUTPUT_LOG_PATH, "w") as f:
        process = subprocess.Popen([constants.CAFFE_HOME + "/build/tools/caffe", "train",
            "--solver=" + constants.SOLVER_FILE, "--weights=" + constants.WEIGHTS_FINETUNED],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        for line in iter(process.stdout.readline, ''):
            sys.stdout.write(line)
            f.write(line)

        print("\t\tTraining output saved to %s" % constants.OUTPUT_LOG_PATH)

def _generate_parsed_logs():
    """
    Takes the raw Caffe output created while training the model in order
    to generate reduced statistics, such as giving iterations vs. test loss.
    """

    print("\tParsing logs...")
    process = subprocess.Popen([constants.CAFFE_HOME + "/tools/extra/parse_log.py",
        constants.OUTPUT_LOG_PATH, constants.LOG_DIR], stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    for line in iter(process.stdout.readline, ''):
        sys.stdout.write(line)

    shutil.rmtree(constants.OUTPUT_LOG_PATH + ".validate", ignore_errors=True)
    shutil.move(constants.OUTPUT_LOG_PATH + ".test",
        constants.OUTPUT_LOG_PATH + ".validate")

    # Convert the commas in the files into tabs to make them easier to read.
    log_files = [constants.OUTPUT_LOG_PATH + ".train",
        constants.OUTPUT_LOG_PATH + ".validate"]
    for line in fileinput.input(log_files, inplace=True):
        line = line.replace(u",", u"\t")
        if fileinput.isfirstline():
            # HACK(neuberg): The column headers with tabs don't quite line up, so shorten
            # some column names and add a tab.
            line = line.replace(u"NumIters", u"Iters")
            line = line.replace(u"LearningRate", u"\tLR")

        sys.stdout.write(line)
    fileinput.close()

    logs = [
        {"title": "Testing", "filename": "train"},
        {"title": "Validation", "filename": "validate"}
    ]
    for log in logs:
        print("\n\t\tParsed %s log:" % log["title"])
        with open(constants.OUTPUT_LOG_PATH + "." + log["filename"], "r") as f:
            lines = f.read().split("\n")
            for line in lines:
                print("\t\t\t%s" % line)

    print("\t\tParsed training log saved to %s" % (constants.OUTPUT_LOG_PATH + ".train"))
    print("\t\tParsed validation log saved to %s\n" % (constants.OUTPUT_LOG_PATH + ".validate"))

def _parse_logs():
    """
    Parses our training and validation logs in order to return them in a way we can work with.
    """
    training_iters = []
    training_loss = []
    training_accuracy = []
    for line in csv.reader(open(constants.OUTPUT_LOG_PATH + ".train"), delimiter="\t",
                            skipinitialspace=True):
        if re.search("Iters", str(line)):
            continue

        training_iters.append(int(float(line[0])))
        training_accuracy.append(float(line[3]))
        training_loss.append(float(line[4]))

    validation_iters = []
    validation_loss = []
    validation_accuracy = []
    for line in csv.reader(open(constants.OUTPUT_LOG_PATH + ".validate"), delimiter="\t",
                            skipinitialspace=True):
        if re.search("Iters", str(line)):
            continue

        validation_iters.append(int(float(line[0])))
        validation_accuracy.append(float(line[3]))
        validation_loss.append(float(line[4]))

    return (
        {
            "iters": training_iters,
            "loss": training_loss,
            "accuracy": training_accuracy
        }, {
            "iters": validation_iters,
            "loss": validation_loss,
            "accuracy": validation_accuracy
        }
    )