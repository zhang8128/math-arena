#include <cadical.hpp>

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <climits>
#include <cstdlib>
#include <exception>
#include <fstream>
#include <iostream>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_set>
#include <vector>

namespace {

struct Formula {
  int variables = 0;
  std::vector<std::vector<int>> clauses;
};

std::string trim(const std::string &input) {
  const std::string whitespace = " \t\r\n";
  const size_t first = input.find_first_not_of(whitespace);
  if (first == std::string::npos) return "";
  const size_t last = input.find_last_not_of(whitespace);
  return input.substr(first, last - first + 1);
}

long parse_integer(const std::string &token, const std::string &context) {
  if (token.empty()) throw std::runtime_error("empty integer in " + context);
  errno = 0;
  char *end = nullptr;
  const long value = std::strtol(token.c_str(), &end, 10);
  if (errno == ERANGE || value < INT_MIN || value > INT_MAX ||
      end != token.c_str() + token.size()) {
    throw std::runtime_error("invalid integer '" + token + "' in " + context);
  }
  return value;
}

Formula read_dimacs(const std::string &path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot read DIMACS file: " + path);

  Formula formula;
  bool saw_header = false;
  int declared_clauses = -1;
  std::vector<int> current_clause;
  std::string line;
  size_t line_number = 0;
  while (std::getline(input, line)) {
    ++line_number;
    const std::string stripped = trim(line);
    if (stripped.empty() || stripped[0] == 'c') continue;
    if (!saw_header) {
      std::istringstream header(stripped);
      std::string p, kind, variables, clauses, trailing;
      if (!(header >> p >> kind >> variables >> clauses) ||
          (header >> trailing) || p != "p" || kind != "cnf") {
        throw std::runtime_error("invalid DIMACS header on line " +
                                 std::to_string(line_number));
      }
      const long parsed_variables = parse_integer(variables, "DIMACS header");
      const long parsed_clauses = parse_integer(clauses, "DIMACS header");
      if (parsed_variables < 0 || parsed_clauses < 0) {
        throw std::runtime_error("negative DIMACS header count");
      }
      formula.variables = static_cast<int>(parsed_variables);
      declared_clauses = static_cast<int>(parsed_clauses);
      saw_header = true;
      continue;
    }

    std::istringstream literals(stripped);
    std::string token;
    while (literals >> token) {
      if (static_cast<int>(formula.clauses.size()) >= declared_clauses &&
          current_clause.empty()) {
        throw std::runtime_error("trailing token after declared DIMACS clauses");
      }
      const long parsed = parse_integer(token, "DIMACS clause");
      if (parsed == 0) {
        formula.clauses.push_back(current_clause);
        current_clause.clear();
      } else {
        if (std::labs(parsed) > formula.variables) {
          throw std::runtime_error("DIMACS literal outside declared range");
        }
        current_clause.push_back(static_cast<int>(parsed));
      }
    }
  }
  if (!input.eof()) throw std::runtime_error("error while reading DIMACS file");
  if (!saw_header) throw std::runtime_error("missing DIMACS header");
  if (!current_clause.empty()) throw std::runtime_error("unterminated DIMACS clause");
  if (static_cast<int>(formula.clauses.size()) != declared_clauses) {
    throw std::runtime_error("DIMACS clause count differs from header");
  }
  return formula;
}

std::vector<int> read_selectors(const std::string &path, int variables) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot read selector file: " + path);
  std::vector<int> selectors;
  std::unordered_set<int> seen;
  std::string line;
  size_t line_number = 0;
  while (std::getline(input, line)) {
    ++line_number;
    const std::string stripped = trim(line);
    if (stripped.empty()) continue;
    std::istringstream tokens(stripped);
    std::string token, trailing;
    if (!(tokens >> token) || (tokens >> trailing)) {
      throw std::runtime_error("selector line must contain exactly one integer");
    }
    const long parsed = parse_integer(token, "selector line " +
                                               std::to_string(line_number));
    if (parsed <= 0 || parsed > variables) {
      throw std::runtime_error("selector must be positive and in variable range");
    }
    const int selector = static_cast<int>(parsed);
    if (!seen.insert(selector).second) {
      throw std::runtime_error("duplicate selector");
    }
    selectors.push_back(selector);
  }
  if (!input.eof()) throw std::runtime_error("error while reading selector file");
  if (selectors.empty()) throw std::runtime_error("selector file is empty");
  return selectors;
}

const char *status_name(int status) {
  if (status == 10) return "SAT";
  if (status == 20) return "UNSAT";
  throw std::runtime_error("CaDiCaL returned UNKNOWN");
}

struct Runner {
  CaDiCaL::Solver solver;
  int solve_calls = 0;

  int solve(const std::vector<int> &assumptions) {
    for (const int literal : assumptions) solver.assume(literal);
    ++solve_calls;
    const int status = solver.solve();
    if (status != 10 && status != 20) {
      throw std::runtime_error("CaDiCaL returned UNKNOWN");
    }
    if (const char *progress_path = std::getenv("T26_PROGRESS_PATH")) {
      std::ofstream progress(progress_path, std::ios::app);
      progress << solve_calls << ' ' << assumptions.size() << ' '
               << status_name(status) << '\n';
    }
    return status;
  }

  std::vector<int> failed_subset(const std::vector<int> &assumptions) {
    std::vector<int> result;
    for (const int literal : assumptions) {
      if (solver.failed(literal)) result.push_back(literal);
    }
    return result;
  }

};

std::vector<int> without_index(const std::vector<int> &values, size_t removed);

struct PlainRunner {
  const Formula &formula;
  const std::unordered_set<int> selector_variables;
  std::atomic<int> solve_calls{0};
  std::mutex progress_mutex;

  PlainRunner(const Formula &input, const std::vector<int> &selectors)
      : formula(input), selector_variables(selectors.begin(), selectors.end()) {}

  int solve(const std::vector<int> &active) {
    const std::unordered_set<int> enabled(active.begin(), active.end());
    CaDiCaL::Solver solver;
    for (const auto &clause : formula.clauses) {
      const bool guarded = !clause.empty() && clause.front() < 0 &&
                           selector_variables.count(-clause.front());
      if (!guarded) {
        solver.clause(clause);
      } else if (enabled.count(-clause.front())) {
        if (clause.size() == 1) {
          solver.clause(std::vector<int>());
        } else {
          solver.clause(clause.data() + 1, clause.size() - 1);
        }
      }
    }
    const int call_number = ++solve_calls;
    const int status = solver.solve();
    if (status != 10 && status != 20) {
      throw std::runtime_error("CaDiCaL returned UNKNOWN");
    }
    if (const char *progress_path = std::getenv("T26_PROGRESS_PATH")) {
      std::lock_guard<std::mutex> lock(progress_mutex);
      std::ofstream progress(progress_path, std::ios::app);
      progress << call_number << ' ' << active.size() << ' '
               << status_name(status) << '\n';
    }
    return status;
  }

  std::vector<int> solve_deletions(const std::vector<int> &core,
                                   size_t worker_count) {
    std::vector<int> statuses(core.size(), 0);
    std::atomic<size_t> next{0};
    std::atomic<bool> stopped{false};
    std::exception_ptr failure;
    std::mutex failure_mutex;
    std::vector<std::thread> workers;
    for (size_t worker = 0; worker < worker_count; ++worker) {
      workers.emplace_back([&]() {
        try {
          while (!stopped.load()) {
            const size_t index = next.fetch_add(1);
            if (index >= core.size()) break;
            statuses[index] = solve(without_index(core, index));
          }
        } catch (...) {
          stopped.store(true);
          std::lock_guard<std::mutex> lock(failure_mutex);
          if (!failure) failure = std::current_exception();
        }
      });
    }
    for (auto &worker : workers) worker.join();
    if (failure) std::rethrow_exception(failure);
    return statuses;
  }
};

std::vector<int> without_index(const std::vector<int> &values, size_t removed) {
  std::vector<int> result;
  result.reserve(values.size() - 1);
  for (size_t i = 0; i < values.size(); ++i) {
    if (i != removed) result.push_back(values[i]);
  }
  return result;
}

std::vector<std::pair<size_t, size_t>> partitions(size_t size, size_t count) {
  std::vector<std::pair<size_t, size_t>> result;
  const size_t width = (size + count - 1) / count;
  for (size_t begin = 0; begin < size; begin += width) {
    result.push_back({begin, std::min(size, begin + width)});
  }
  return result;
}

std::vector<int> without_range(const std::vector<int> &values, size_t begin,
                               size_t end) {
  std::vector<int> result;
  result.reserve(values.size() - (end - begin));
  result.insert(result.end(), values.begin(), values.begin() + begin);
  result.insert(result.end(), values.begin() + end, values.end());
  return result;
}

void print_integer_array(const std::vector<int> &values) {
  std::cout << '[';
  for (size_t i = 0; i < values.size(); ++i) {
    if (i) std::cout << ',';
    std::cout << values[i];
  }
  std::cout << ']';
}

}  // namespace

int main(int argc, char **argv) {
  try {
    if (argc != 4) {
      throw std::runtime_error(
          "usage: t26_group_mus FORMULA SELECTORS extract|verify|seed");
    }
    const std::string mode = argv[3];
    if (mode != "extract" && mode != "verify" && mode != "seed") {
      throw std::runtime_error("unsupported mode: " + mode);
    }

    const Formula formula = read_dimacs(argv[1]);
    const std::vector<int> requested = read_selectors(argv[2], formula.variables);
    if (mode == "seed") {
      Runner runner;
      for (const auto &clause : formula.clauses) runner.solver.clause(clause);
      if (runner.solve(requested) != 20) {
        throw std::runtime_error("requested selector set is not UNSAT");
      }
      const std::vector<int> seed = runner.failed_subset(requested);
      if (seed.empty()) throw std::runtime_error("empty failed-assumption core");
      std::cout << "{\"status\":\"UNSAT\",\"cadical_version\":\""
                << CaDiCaL::Solver::version() << "\",\"input_variables\":"
                << formula.variables << ",\"input_clauses\":"
                << formula.clauses.size() << ",\"requested_selectors\":";
      print_integer_array(requested);
      std::cout << ",\"core_selectors\":";
      print_integer_array(seed);
      std::cout << ",\"deletion_statuses\":[],\"solve_calls\":"
                << runner.solve_calls << "}\n";
      return 0;
    }
    std::vector<int> core = requested;
    std::vector<int> deletion_statuses;
    int solve_calls = 0;
    const size_t extraction_workers = 8;
    std::string deletion_algorithm = "incremental-verification";
    size_t reported_workers = 1;
    if (mode == "extract") {
      deletion_algorithm = "parallel-batch-ddmin";
      reported_workers = extraction_workers;
      PlainRunner runner(formula, requested);
      if (runner.solve(core) != 20) {
        throw std::runtime_error("requested selector set is not UNSAT");
      }
      size_t granularity = 2;
      bool terminal_deletions_checked = false;
      bool use_batch_deletion = false;
      while (core.size() >= 2) {
        bool reduced = false;
        for (const auto [begin, end] : partitions(core.size(), granularity)) {
          const std::vector<int> trial = without_range(core, begin, end);
          if (runner.solve(trial) == 20) {
            core = trial;
            granularity = std::max<size_t>(2, granularity - 1);
            reduced = true;
            break;
          }
        }
        if (!reduced) {
          if (granularity >= core.size()) {
            terminal_deletions_checked = true;
            break;
          }
          if (granularity >= 8) {
            use_batch_deletion = true;
            break;
          }
          granularity = std::min(core.size(), granularity * 2);
        }
      }
      if (use_batch_deletion) {
        while (true) {
          const std::vector<int> statuses =
              runner.solve_deletions(core, extraction_workers);
          const auto removable = std::find(statuses.begin(), statuses.end(), 20);
          if (removable == statuses.end()) break;
          core = without_index(core, removable - statuses.begin());
        }
        terminal_deletions_checked = true;
      }
      if (core.empty()) {
        throw std::runtime_error("final core is not UNSAT");
      }
      deletion_statuses.reserve(core.size());
      if (terminal_deletions_checked) {
        deletion_statuses.assign(core.size(), 10);
      } else {
        for (size_t index = 0; index < core.size(); ++index) {
          const int deletion_status = runner.solve(without_index(core, index));
          if (deletion_status != 10) {
            throw std::runtime_error("extracted core is not deletion-irreducible");
          }
          deletion_statuses.push_back(deletion_status);
        }
      }
      solve_calls = runner.solve_calls.load();
    } else {
      Runner runner;
      for (const auto &clause : formula.clauses) runner.solver.clause(clause);
      if (runner.solve(core) != 20) {
        throw std::runtime_error("requested selector set is not UNSAT");
      }
      if (runner.solve(core) != 20) {
        throw std::runtime_error("final core is not UNSAT");
      }
      deletion_statuses.reserve(core.size());
      for (size_t index = 0; index < core.size(); ++index) {
        deletion_statuses.push_back(runner.solve(without_index(core, index)));
      }
      solve_calls = runner.solve_calls;
    }

    std::cout << '{';
    std::cout << "\"status\":\"UNSAT\",";
    std::cout << "\"cadical_version\":\"" << CaDiCaL::Solver::version()
              << "\",";
    std::cout << "\"input_variables\":" << formula.variables << ',';
    std::cout << "\"input_clauses\":" << formula.clauses.size() << ',';
    std::cout << "\"requested_selectors\":";
    print_integer_array(requested);
    std::cout << ",\"core_selectors\":";
    print_integer_array(core);
    std::cout << ",\"deletion_statuses\":[";
    for (size_t index = 0; index < core.size(); ++index) {
      if (index) std::cout << ',';
      std::cout << "{\"selector\":" << core[index] << ",\"status\":\""
                << status_name(deletion_statuses[index]) << "\"}";
    }
    std::cout << "],\"solve_calls\":" << solve_calls
              << ",\"deletion_algorithm\":\"" << deletion_algorithm
              << "\",\"worker_count\":" << reported_workers << "}\n";
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "t26_group_mus: " << error.what() << '\n';
    return 2;
  }
}
