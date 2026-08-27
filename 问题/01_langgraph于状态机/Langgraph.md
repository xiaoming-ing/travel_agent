### 01.为什么用LangGraph而不是自己写循环/用LangChain
我需要有状态的多轮对话（澄清->规划->反馈->修改），每轮要暂停等用户输入，还要能中断恢复。Langchain只支持单轮ReAct循环，自己写循环的话状态持久化、中断恢复、流式事件都需要自己从头造轮子。LangGraph的StateGraph原生支持interrupt(暂停图等输入)和checkpoint(持久化到SQLite)，而且astream_events能穿透嵌套Agent拿到内部工具调用进度，正好满足我SSE实时推送进度到需求。

### 02.LangGraph的StateGraph和普通状态机有啥区别
普通状态机只定义“状态+转移规则”，LangGraph的StateGraph每个节点是一个函数（能调LLM，工具，数据库），函数return的dict会合并到state里（不是覆盖），边可以是条件边函数（根据state内容动态决定下一跳），而且内置啦checkpoint持久化和流事件，专为LLM Agent工作流设计

### 03.图有那几个节点？画一下流转
- START后无条件进clarify
- clarify后走条件边should_continue:信息全->plan,不全 -> 回clarify
- plan 后无条件进feedback
- feedback interrupt等用户输入，然后走条件边should_revise:用户满意->END，否则->revise
- revise改完后feedback（形成循环）

### 04.条件边是怎么决定走revise还是END?
should_revise函数拿到state里的last_feedback,判断是不是done_words(["满意","done"]),是就返回"__end__",否则返回"revise"。LangGraph根据返回值走对应的边。

### 05.interrupt怎么实现 暂停图、等用户输入的？底层机制
interrupt(value)调用后，LangGraph会抛出一个特殊异常（内部捕获不传播），把当前state+中断点位置写进checkpoint,然后停止图的执行、把value（我这里是{type,question,trip_plan}）返回给调用方。前端拿到后展示给用户。用户输入后，用Command(resume=用户输入)重新调图，LangGraph从checkpoint恢复到中断点，把用户输入作为interrupt的返回值继续跑。

### 06.暂停后，图的状态存在哪里？下次resume怎么恢复到中断点的？
存在checkpoint(我用的SqliteSaver,写进去checkpoints.db的checkpoints表)。每个会话有一个thread_id,checkpoint按(thread_id,checkpoint_id)存，记录了当前state、执行到哪个节点、peding的tasks、配置(config)。resume时传同一个thread_id,LangGraph读最新的checkpoint,恢复state,从中断点的下一步继续执行，保存的是中断点之前的完整状态。

### 07.服务器重启了，用户还能接着上次的对话吗，为什么
能。因为checkpoint持久化存在SQLite里，不在内存。只要checkpoints.db还在、thread_id没变，重启后再调用图、传同一个thread_id,LangGraph会从数据库读checkpoint恢复。

### 08.checkpoint是什么？用它存了啥
checkpoint是LangGraph的状态快照机制，每执行完一个节点就自动保存一次。我用SqliteSaver把checkpoint存进SQlite，里面有：当前state(用户请求、行程】候选数据、token消耗)、执行位置(刚跑完哪个节点、下一步该跑谁)。主要用途是interrupt后恢复(用户中断对话、重启服务都能接着聊)和历史会话查询。

### 09.thread_id的作用？多个用户并发会串吗？
thread_id是会话隔离标识，每个用户的每次对话用唯一thread_id(我用UUID生成的)。checkpoint按thread_id分组存，LangGraph读写checkpoint时只操作这个thread的数据，不同thread完全隔离、不会串。

### 10.为什么部署时必须--workers1？不加会咋样
SqliteSaver用的aiosqlit,SQLite同一时刻只允许一个写事务。如果开多个worker,不同进程同时写checkpointe吹触发database is locked错误，导致图执行失败。--workers1 保证单进程写，避免并发冲突。

### 11.state和config有啥区别？usr_id为啥走config不走state
state是图的业务数据，会被节点函数读写、merge更新；config是图的元信息/配置，只读、不被节点修改。
user_id放config的原因
- 它是身份标识、不是业务状态，整个会话固定不变
- LangGraph会把config自动透传给嵌套agent,不用手动在state传
- checkpoint会保存config,回复时候自动带上user_id,省的在state里维护。


### 12.LangGraph Event 怎么发送？
- 自动发送：LangGraph内置事件（工具调用、节点执行），这些是图执行过程中自动产生的
我们在astream_events可以捕获，，再转换yield给前端
- 手动发送：自己定义的事件，需要通过dispatch_custom_event塞进当前正在跑的callback事件流里，才能在astream_events里捕获