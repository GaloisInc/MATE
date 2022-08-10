#!/bin/env ruby

require "expect"
require "logger"
require "securerandom"

LLL = Logger.new(STDERR,
                 formatter: proc do |sev, datetime, progname, msg|
                   "#{sev}: #{msg}\n"
                 end)

class Poller
  PRE_LOGIN_ACTIVITIES = %i{
                           list_users
                           login_to_real_user
                           login_to_fake_user
                           fail_check_messages
                           fail_send_to
                           }
  POST_LOGIN_ACTIVITIES = %i{
                            list_users
                            login_to_real_user login_to_fake_user
                            send_to_real_user send_to_fake_user
                            check_messages
                            }

  def initialize
    @host = ENV['HOST']
    @port = ENV['PORT'].to_i
    seed_rng!
    pick_length!

    @sent_messages = Hash.new
    @available_activities = PRE_LOGIN_ACTIVITIES
  end

  def run!
    connect!
    wait_prompt

    @length.times do
      my_activity = @available_activities.sample
      LLL.debug "Trying #{my_activity}"
      send my_activity
    end
  end

  private
  def login_to_real_user
    @current_user = users.sample
    @in.puts "LOGIN #{@current_user}"
    login_confirm = wait_prompt.lines[0]

    unless "logged in as #{@current_user}" == login_confirm.strip
      LLL.fatal login_confirm
      die("failed to log in as #{@current_user}")
    end

    LLL.debug "Logged in as #{@current_user}"
    @available_activities = POST_LOGIN_ACTIVITIES
  end

  def login_to_fake_user
    attempt_user = fake_user

    @in.puts "LOGIN #{attempt_user}"
    login_result = wait_prompt.lines[0]
    unless /failed to log in as user/ =~ login_result
      LLL.fatal login_result
      die("failed to fail to log in as #{attempt_user}")
    end

    LLL.debug "didn't log in as #{attempt_user}"
    if @current_user
      LLL.debug "(should still be #{@current_user})"
    end
  end

  def send_to_real_user
    target = users.sample
    message = Message.new(@current_user, target)
    LLL.debug "sending #{message.inspect}"
    @in.puts "SEND #{target}"

    unless @out.expect("enter message to #{target}:\n", 5)
      die("didn't get 'enter message' prompt")
    end

    @in.puts message.contents
    delivery_confirmation = wait_prompt
    unless delivery_confirmation.lines[0] == "message will be delivered later\n"
      die("didn't get message delivery notice")
    end

    unless @sent_messages[target]
      @sent_messages[target] = Array.new
    end

    @sent_messages[target] << message
  end

  def send_to_fake_user
    attempt_fake = fake_user
    @in.puts "SEND #{attempt_fake}"
    refusal = wait_prompt.lines[0].strip

    if "couldn't find recipient #{attempt_fake}" != refusal
      LLL.fatal refusal
      die("didn't get expected refusal for SEND to #{attempt_fake}")
    end
  end

  def fail_send_to
    @in.puts "SEND #{fake_user}"
    refusal = wait_prompt.lines[0].strip

    if "cannot send messages without being logged in" != refusal
      LLL.fatal refusal
      die("didn't get expected refusal for SEND while logged out'")
    end
  end

  def list_users
    # if no users, just see if we get a list
    return list_users_first unless defined? @users

    @in.puts "LIST"
    current_list = wait_prompt.lines[0..-2].map(&:strip)
    if users != current_list
      LLL.fatal "expected #{users.inspect}"
      LLL.fatal "got #{current_list.inspect}"
      die("got unexpected user list")
    end
  end

  def list_users_first
    if users.length == 0
      die "didn't get a sensical list of users"
    end
  end

  def check_messages
    expecting = @sent_messages[@current_user]

    unless expecting
      LLL.info "not expecting messages necessarily"
      @in.puts "INBOX"
      messages = wait_prompt.lines[1..-3].map(&:strip)
      LLL.debug messages.inspect
      @sent_messages[@current_user] = messages.map do |msg|
        message_data = /from ([^:]+): (.+)$/.match msg
        Message.new(message_data[1], @current_user, message_data[2])
      end

      LLL.info "remembering #{@sent_messages[@current_user].inspect}"
    end
  end

  def fail_check_messages
    @in.puts "INBOX"
    refusal = wait_prompt.lines[0].strip

    if "cannot check inbox without being logged in" != refusal
      LLL.fatal refusal
      die "didn't get INBOX-without-logged-in notice'"
    end
  end

  def users
    return @users if defined? @users
    @in.puts "LIST"
    @users = wait_prompt.lines[0..-2].map(&:strip)
    LLL.debug "found users #{@users.inspect}"
    return @users
  end

  def fake_user
    attempt_fake = users.first
    while users.include? attempt_fake
      attempt_fake = rand(36**10).to_s(36)
    end

    return attempt_fake
  end

  def wait_prompt
    (@out.expect("bryant> ", timeout=5) or die("didn't get prompt'")).join
  end

  def connect!
    if @host.nil?
      LLL.info "launching myself"

      bin_path = ENV['BIN_PATH']

      if bin_path.nil?
        bin_path = File.absolute_path("../build/bryant", __dir__)
      end

      LLL.info "starting #{bin_path}"

      require "open3"
      @in, @out, @err, @wait = Open3.popen3(bin_path)

      Thread.new do
        loop do
          begin
            got = @err.read 80
            LLL.info "stderr: #{got}"
          rescue IO::WaitReadable
          end
        end
      end
    else
      puts "connecting to #{@host}:#{@port}"
      require "socket"

      sock = TCPSocket.new @host, @port
      sock.setsockopt(Socket::IPPROTO_TCP, Socket::TCP_NODELAY, true)
      @in = sock
      @out = sock
    end
  end

  def die(message)
    LLL.fatal message
    exit -1
  end

  def seed_rng!
    seed = (ENV['SEED'] || Random.new_seed).to_i
    $stdout.puts "SEED=#{seed}"
    srand(seed)
  end

  def pick_length!
    @length = (ENV['LENGTH'] || (50..100).to_a.sample).to_i
    $stdout.puts "LENGTH=#{@length}"
  end
end

class Message
  WORDS = %w{
             refrigerator cornflakes bike eat broccoli lamp superman light
             workout mug coffee brew roast comedian jacket pants tp remote
             glass pint explain explainer controller laptop desktop love
             compute server bag notebook cube speaker annoy please thank shoe
             tape sword ink solder chair sit toilet break fix cat dog the and a
             an one pluralize
             }
  attr_reader :sender, :recipient, :contents
  def initialize(sender, recipient, contents = nil)
    @sender = sender
    @recipient = recipient
    @contents = contents || WORDS.sample(10).join(" ")
  end
end

Poller.new.run!
